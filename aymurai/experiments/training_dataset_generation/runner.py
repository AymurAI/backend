from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from aymurai.experiments.mlflow_utils import (
    configure_mlflow,
    safe_end_run,
    safe_log_artifacts,
    safe_log_metrics,
    safe_log_params,
    safe_set_tags,
    safe_start_run,
)
from aymurai.experiments.training_dataset_generation.config import (
    TrainingDatasetGenerationConfig,
    build_strategy_slug,
    load_training_dataset_generation_config,
    render_run_dir_name,
)
from aymurai.experiments.training_dataset_generation.core import (
    build_dataset_composition_report,
    calculate_train_set_stats,
    export_jsonl,
    filter_labeled_candidates,
    load_candidates_from_paths,
    paragraphs_from_bio,
    parse_bio_paragraphs,
    perform_corpus_deduplication,
    perform_internal_deduplication,
    resolve_target_labels,
    sample_unlabeled_candidates,
    shuffle_candidates,
    write_bio_dataset,
)


def log_step(message: str) -> None:
    print(f"[training-dataset-generation] {message}")


def prepare_run_directory(config: TrainingDatasetGenerationConfig) -> Path:
    strategy_slug = build_strategy_slug(config)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir_name = render_run_dir_name(
        config.paths.run_dir_name_template,
        timestamp=timestamp,
        strategy=strategy_slug,
    )
    run_dir = Path(config.paths.output_dir) / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_pipeline(config: TrainingDatasetGenerationConfig) -> dict:
    run_dir = prepare_run_directory(config)
    mlflow_enabled, mlflow_experiment_id = configure_mlflow(config.logging.mlflow)

    if mlflow_enabled:
        mlflow_enabled = safe_start_run(
            run_name=run_dir.name,
            experiment_id=mlflow_experiment_id,
        )

        safe_set_tags(
            {
                "experiment": "training-dataset-generation",
                "run_dir": str(run_dir),
                "strategy": build_strategy_slug(config),
            }
        )

        safe_log_params(
            {
                "run_dir_name": run_dir.name,
                "strategy_slug": build_strategy_slug(config),
                "label_selection_mode": config.label_selection.mode,
                "low_frequency_top_k": config.label_selection.low_frequency_top_k,
                "unlabeled_sampling_mode": config.unlabeled_sampling.mode,
                "target_background_to_labeled_ratio": (
                    config.unlabeled_sampling.target_background_to_labeled_ratio
                ),
                "include_original_train": config.assembly.include_original_train,
                "internal_dedup_threshold": config.deduplication.internal_threshold,
                "corpus_dedup_threshold": config.deduplication.corpus_threshold,
            }
        )

    log_step(f"Writing artifacts to {run_dir}")

    train_paragraphs = paragraphs_from_bio(config.paths.train_set_path)
    dev_paragraphs = paragraphs_from_bio(config.paths.dev_set_path)
    test_paragraphs = paragraphs_from_bio(config.paths.test_set_path)
    all_existing_text = (
        set(train_paragraphs) | set(dev_paragraphs) | set(test_paragraphs)
    )

    parsed_train = parse_bio_paragraphs(config.paths.train_set_path)
    original_train_stats = calculate_train_set_stats(parsed_train)
    log_step(
        "Loaded original corpus: "
        f"train={len(train_paragraphs)}, dev={len(dev_paragraphs)}, test={len(test_paragraphs)}"
    )

    new_candidates = load_candidates_from_paths(config.paths.candidate_input_paths)
    log_step(
        f"Loaded {len(new_candidates)} raw candidates from "
        f"{len(config.paths.candidate_input_paths)} input path(s)"
    )

    unique_candidates, internal_duplicates = perform_internal_deduplication(
        new_candidates,
        threshold=config.deduplication.internal_threshold,
    )
    (
        clean_labeled,
        clean_unlabeled,
        duplicates_with_labels,
        duplicates_without_labels,
        discarded_noise,
    ) = perform_corpus_deduplication(
        unique_candidates,
        all_existing_text,
        threshold=config.deduplication.corpus_threshold,
    )

    target_labels = resolve_target_labels(
        original_train_stats=original_train_stats,
        low_frequency_labels_path=config.paths.low_frequency_labels_path,
        low_frequency_top_k=config.label_selection.low_frequency_top_k,
    )
    selected_labeled = filter_labeled_candidates(
        clean_labeled,
        mode=config.label_selection.mode,
        target_labels=set(target_labels),
        min_target_labels_per_candidate=config.label_selection.min_target_labels_per_candidate,
    )
    selected_unlabeled = sample_unlabeled_candidates(
        clean_unlabeled,
        selected_labeled_count=len(selected_labeled),
        original_train_stats=original_train_stats,
        include_original_train=config.assembly.include_original_train,
        mode=config.unlabeled_sampling.mode,
        target_background_to_labeled_ratio=(
            config.unlabeled_sampling.target_background_to_labeled_ratio
        ),
        fixed_count=config.unlabeled_sampling.fixed_count,
        seed=config.assembly.seed,
    )

    selected_candidates = [*selected_labeled, *selected_unlabeled]
    if config.assembly.shuffle_selected_candidates:
        selected_candidates = shuffle_candidates(
            selected_candidates, seed=config.assembly.seed
        )

    clean_labeled_path = run_dir / config.paths.clean_labeled_filename
    clean_unlabeled_path = run_dir / config.paths.clean_unlabeled_filename
    selected_candidates_path = run_dir / config.paths.selected_candidates_filename
    final_bio_path = run_dir / config.paths.final_bio_filename
    report_path = run_dir / config.paths.report_filename
    dataset_composition_report_path = (
        run_dir / config.paths.dataset_composition_report_filename
    )
    low_frequency_labels_output_path = (
        run_dir / config.paths.low_frequency_labels_filename
    )

    export_jsonl(clean_labeled, clean_labeled_path)
    export_jsonl(clean_unlabeled, clean_unlabeled_path)
    export_jsonl(selected_candidates, selected_candidates_path)
    low_frequency_labels_output_path.write_text(
        "\n".join(target_labels) + "\n", encoding="utf-8"
    )

    bio_write_stats = write_bio_dataset(
        original_train_path=config.paths.train_set_path,
        selected_candidates=selected_candidates,
        output_path=final_bio_path,
        include_original_train=config.assembly.include_original_train,
    )

    dataset_composition_report = build_dataset_composition_report(
        generated_dataset_path=final_bio_path,
        base_train_path=config.paths.train_set_path,
    )
    dataset_composition_report_path.write_text(
        json.dumps(dataset_composition_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log_step(f"Saved dataset composition report to {dataset_composition_report_path}")

    report = {
        "run_dir": str(run_dir),
        "strategy_slug": build_strategy_slug(config),
        "input_paths": {
            "train_set_path": config.paths.train_set_path,
            "dev_set_path": config.paths.dev_set_path,
            "test_set_path": config.paths.test_set_path,
            "candidate_input_paths": config.paths.candidate_input_paths,
            "low_frequency_labels_path": config.paths.low_frequency_labels_path,
        },
        "selection_config": config.model_dump(mode="json"),
        "original_train_stats": {
            "total_paragraphs": original_train_stats.total_paragraphs,
            "labeled_count": original_train_stats.labeled_count,
            "unlabeled_count": original_train_stats.unlabeled_count,
            "background_ratio": original_train_stats.background_ratio,
            "low_frequency_labels": target_labels,
        },
        "candidate_flow": {
            "raw_candidates": len(new_candidates),
            "unique_candidates_after_internal_dedup": len(unique_candidates),
            "internal_duplicates": len(internal_duplicates),
            "clean_labeled": len(clean_labeled),
            "clean_unlabeled": len(clean_unlabeled),
            "duplicates_with_labels": len(duplicates_with_labels),
            "duplicates_without_labels": len(duplicates_without_labels),
            "discarded_noise": len(discarded_noise),
            "selected_labeled": len(selected_labeled),
            "selected_unlabeled": len(selected_unlabeled),
            "selected_total": len(selected_candidates),
        },
        "artifacts": {
            "clean_labeled_jsonl": str(clean_labeled_path),
            "clean_unlabeled_jsonl": str(clean_unlabeled_path),
            "selected_candidates_jsonl": str(selected_candidates_path),
            "final_bio_path": str(final_bio_path),
            "low_frequency_labels_path": str(low_frequency_labels_output_path),
            "report_path": str(report_path),
            "dataset_composition_report_path": str(dataset_composition_report_path),
        },
        "bio_write_stats": bio_write_stats,
        "dataset_composition_report": dataset_composition_report,
    }

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if mlflow_enabled:
        safe_log_metrics(
            {
                "raw_candidates": float(len(new_candidates)),
                "unique_candidates_after_internal_dedup": float(len(unique_candidates)),
                "internal_duplicates": float(len(internal_duplicates)),
                "clean_labeled": float(len(clean_labeled)),
                "clean_unlabeled": float(len(clean_unlabeled)),
                "duplicates_with_labels": float(len(duplicates_with_labels)),
                "duplicates_without_labels": float(len(duplicates_without_labels)),
                "discarded_noise": float(len(discarded_noise)),
                "selected_labeled": float(len(selected_labeled)),
                "selected_unlabeled": float(len(selected_unlabeled)),
                "selected_total": float(len(selected_candidates)),
                "bio_appended_candidates": float(
                    bio_write_stats["appended_candidates"]
                ),
                "bio_skipped_candidates": float(bio_write_stats["skipped_candidates"]),
                "generated_dataset_paragraphs": float(
                    dataset_composition_report["generated_dataset_stats"]["paragraphs"]
                ),
                "generated_dataset_labeled_paragraphs": float(
                    dataset_composition_report["generated_dataset_stats"][
                        "labeled_paragraphs"
                    ]
                ),
                "generated_dataset_unlabeled_paragraphs": float(
                    dataset_composition_report["generated_dataset_stats"][
                        "unlabeled_paragraphs"
                    ]
                ),
                "generated_dataset_n_labels": float(
                    dataset_composition_report["generated_dataset_stats"]["n_labels"]
                ),
                "required_labels_present": float(
                    dataset_composition_report["required_labels_present"]
                ),
                "required_labels_missing": float(
                    dataset_composition_report["required_labels_missing"]
                ),
            }
        )
        safe_log_artifacts(run_dir, artifact_path="outputs")
        safe_end_run()
    log_step(f"Saved report to {report_path}")
    log_step(f"Saved final BIO dataset to {final_bio_path}")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate balanced training datasets from notebook-derived logic."
    )
    parser.add_argument(
        "--config", required=True, help="Path to the YAML configuration file."
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = load_training_dataset_generation_config(args.config)
    run_pipeline(config)


if __name__ == "__main__":
    main()
