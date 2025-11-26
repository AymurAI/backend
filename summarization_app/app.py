import json
import re
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

# Set page configuration
st.set_page_config(
    page_title="Document Summarization Experiments",
    page_icon="📄",
    layout="wide",
)


# Function to load the results
@st.cache_data
def load_data(file_path: str):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return []


# Function to extract unique values from the dataset
def get_unique_values(data, field):
    values = set()
    for item in data:
        if field in item:
            values.add(item[field])
    return sorted(list(values))


# Create a helper function to handle None values
def get_sort_key(item, field, sort_order):
    value = item.get(field)
    # Handle None values by putting them at the end
    if value is None:
        return float("inf") if sort_order == "Ascending" else float("-inf")
    return value


# Mapping from UI names to data fields for sorting and plotting
SORT_FIELD_MAP = {
    "Model": "model",
    "Prompt Type": "system_prompt_type",
    "Tokens per Second": "tokens_per_second",
    "Duration": "measured_duration_ms",
    "Input Tokens": "input_tokens",
    "Output Tokens": "output_tokens",
    "Device": "device",
}


# Attempt to identify parameter scale (in billions) from model names
def get_model_parameter_scale(model_name):
    if not model_name:
        return None

    known_params = {
        "gemma3:12b": 12,
        "gemma3:40b": 40,
        "gemma3:20b": 20,
        "gemma3:22b": 22,
        "gemma3:38b": 38,
        "llama3.1:8b": 8,
        "llama3.2:3b": 3,
        "llama3.2:11b": 11,
        "deepseek-r1:1.1b": 1.1,
        "deepseek-r1:1b": 1,
        "phi-3:3.8b": 3.8,
        "phi-4:14b": 14,
        "qwen3:3.8b": 3.8,
        "qwen3:14b": 14,
        "qwen3:72b": 72,
    }

    model_name_lower = model_name.lower()
    if model_name_lower in known_params:
        return known_params[model_name_lower]

    match = re.search(r"(\d+(?:\.\d+)?)\s*b", model_name_lower)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


# Main function
def main():
    st.title("📄 Document Summarization Experiments")

    # File selector
    results_file = st.sidebar.file_uploader("Upload JSON results file", type=["json"])

    if results_file is not None:
        # Load data from uploaded file
        content = results_file.getvalue().decode("utf-8")
        data = json.loads(content)
    else:
        # Try to load from the default path
        default_path = "./summarization-benchmark-results.json"
        if Path(default_path).exists():
            data = load_data(default_path)
            st.sidebar.success(f"Loaded data from {default_path}")
        else:
            st.sidebar.warning("Please upload a JSON results file")
            st.stop()

    # Extract unique values for filters
    models = get_unique_values(data, "model")
    prompt_types = get_unique_values(data, "system_prompt_type")
    doc_paths = get_unique_values(data, "doc_path")
    doc_filenames = {doc_path: Path(doc_path).name for doc_path in doc_paths}
    devices = get_unique_values(data, "device")

    # Create filters in the sidebar
    st.sidebar.header("Filters")

    model_options = ["All"] + models
    default_models = ["All"] if models else []
    selected_models = st.sidebar.multiselect(
        "Select Models", options=model_options, default=default_models
    )
    selected_prompt_type = st.sidebar.selectbox(
        "Select Prompt Type", ["All"] + prompt_types
    )
    selected_doc = st.sidebar.selectbox(
        "Select Document", ["All"] + list(doc_filenames.values())
    )
    selected_device = st.sidebar.selectbox("Select Device", ["All"] + devices)

    # Add metrics display option
    st.sidebar.header("Display Options")
    show_metrics = st.sidebar.checkbox("Show Metrics", value=True)
    show_system_prompt = st.sidebar.checkbox("Show System Prompt", value=False)
    show_raw_response = st.sidebar.checkbox("Show Raw Response", value=False)

    # Sorting options
    st.sidebar.header("Sorting")
    sort_by = st.sidebar.selectbox(
        "Sort by",
        [
            "Default",
            "Model",
            "Prompt Type",
            "Tokens per Second",
            "Duration",
            "Input Tokens",
            "Output Tokens",
            "Device",
        ],
    )
    sort_order = st.sidebar.radio("Sort order", ["Ascending", "Descending"])

    # Filter data based on selections
    filtered_data = data

    if "All" in selected_models:
        if len(selected_models) == 1:
            selected_models_filter = None
        else:
            selected_models_filter = {
                model for model in selected_models if model != "All"
            }
    else:
        selected_models_filter = set(selected_models)

    if selected_models_filter:
        filtered_data = [
            item
            for item in filtered_data
            if item.get("model") in selected_models_filter
        ]

    if selected_prompt_type != "All":
        filtered_data = [
            item
            for item in filtered_data
            if item.get("system_prompt_type") == selected_prompt_type
        ]

    if selected_doc != "All":
        filtered_data = [
            item
            for item in filtered_data
            if doc_filenames.get(item.get("doc_path")) == selected_doc
        ]

    if selected_device != "All":
        filtered_data = [
            item for item in filtered_data if item.get("device") == selected_device
        ]

    # Apply sorting
    if sort_by != "Default":
        field = SORT_FIELD_MAP.get(sort_by)
        if field:
            # Sort the filtered data
            filtered_data = sorted(
                filtered_data,
                key=lambda item: get_sort_key(item, field, sort_order),
                reverse=(sort_order == "Descending"),
            )

    # Display results count
    st.write(f"Found {len(filtered_data)} result(s) out of {len(data)} total.")

    # Pagination controls
    st.sidebar.header("Pagination")
    items_per_page_options = [5, 10, 20, 50, 100, "All"]

    # Create session state for items per page if it doesn't exist
    if "items_per_page" not in st.session_state:
        st.session_state.items_per_page = 10

    # Handle the items per page selection
    selected_items = st.sidebar.selectbox(
        "Results per page",
        options=items_per_page_options,
        index=items_per_page_options.index(
            10 if 10 in items_per_page_options else items_per_page_options[1]
        ),
        key="items_per_page_selector",
    )

    # Handle the "All" option
    if selected_items == "All":
        items_per_page = len(filtered_data)
    else:
        items_per_page = selected_items

    # Update session state
    if st.session_state.items_per_page != items_per_page:
        st.session_state.items_per_page = items_per_page
        st.session_state.current_page = (
            1  # Reset to first page when changing items per page
        )

    total_pages = max(1, (len(filtered_data) + items_per_page - 1) // items_per_page)

    # Create session state for pagination if it doesn't exist
    if "current_page" not in st.session_state:
        st.session_state.current_page = 1

    # Ensure current page is valid after filtering
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = 1

    # Only show pagination controls if there are multiple pages
    if total_pages > 1:
        col_label, col_input, _ = st.columns([1, 1, 6])

        with col_label:
            st.markdown("**Page**")
            st.caption(f"1 - {total_pages}")

        with col_input:
            current_page = st.number_input(
                "Page selector",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.current_page,
                step=1,
                label_visibility="collapsed",
            )
        st.session_state.current_page = current_page
    else:
        st.session_state.current_page = 1

    current_page = st.session_state.current_page

    # Calculate start and end indices for the current page
    start_idx = (current_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered_data))

    # Get the subset of data for the current page
    page_data = filtered_data[start_idx:end_idx]

    # Show page information
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(
            f"Displaying results {start_idx + 1}-{end_idx} of {len(filtered_data)}"
        )

    with col2:
        # If we have multiple pages, show a page indicator
        if total_pages > 1:
            st.write(f"Page {current_page} of {total_pages}")

    # Display the filtered results
    if page_data:
        for idx, result in enumerate(page_data):
            device_tag = (
                f" ({result.get('device', 'N/A')})" if result.get("device") else ""
            )
            title = f"{result.get('model', 'N/A')}{device_tag} - [{result.get('system_prompt_type', 'Unknown')}] - {Path(result.get('doc_path', 'N/A')).name}"

            with st.expander(title):
                # Display metrics as a table in a clean format
                if show_metrics:
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("Summarization Context")
                        context_info = {
                            "Model": result.get("model", "N/A"),
                            "Device": result.get("device", "N/A"),
                            "Prompt Type": result.get("system_prompt_type", "Unknown"),
                            "Document": Path(result.get("doc_path", "N/A")).name,
                        }
                        st.table(pd.DataFrame([context_info]))

                    with col2:
                        st.subheader("Performance Metrics")
                        metrics = {
                            "Input Tokens": result.get("input_tokens", "N/A"),
                            "Output Tokens": result.get("output_tokens", "N/A"),
                            "Total Tokens": result.get("total_tokens", "N/A"),
                            "Tokens/Second": f"{result.get('tokens_per_second', 0):.2f}",
                            "Duration (sec)": f"{result.get('measured_duration_ms', 0) / 1000:.2f}",
                            "Device": result.get("device", "N/A"),
                        }
                        st.table(pd.DataFrame([metrics]))

                if show_system_prompt:
                    st.subheader("System Prompt")
                    st.caption(
                        f"Prompt type: **{result.get('system_prompt_type', 'Unknown')}**"
                    )
                    st.code(
                        result.get("system_prompt", "N/A"),
                        language="markdown",
                    )

                # Display chat response as markdown
                st.subheader("Response")
                st.markdown(result.get("chat_response", "No response available"))

                # Optional: Display raw response as a JSON
                if show_raw_response and "raw_response" in result:
                    st.subheader("Raw Response")
                    st.json(result["raw_response"])

        # Show a summary visualization if more than one result is selected
        if len(filtered_data) > 1:
            st.header("Summary Visualizations")

            # Create a DataFrame for easier analysis
            df = pd.DataFrame(filtered_data)
            df = df.loc[:, ~pd.Index(df.columns).duplicated()]
            if "model" in df.columns:
                df["model"] = df["model"].apply(
                    lambda value: (
                        value
                        if isinstance(value, str)
                        else str(value)
                        if value is not None
                        else "Unknown"
                    )
                )
            if "doc_path" in df.columns:
                df["document_name"] = df["doc_path"].apply(
                    lambda p: Path(p).name if isinstance(p, str) else "Unknown"
                )
            else:
                df["document_name"] = "Unknown"
            df["model_params_b"] = df["model"].apply(get_model_parameter_scale)
            df["total_duration_sec"] = df["measured_duration_ms"] / 1000

            # Determine ordering for models in visualizations based on sorting
            if "model" in df.columns:
                model_values = df["model"].dropna().unique().tolist()
            else:
                model_values = []
            model_order = model_values.copy()
            sort_field = SORT_FIELD_MAP.get(sort_by)
            ascending = sort_order == "Ascending"

            if sort_by == "Model":
                model_order = sorted(model_values, reverse=not ascending)
            elif (
                sort_field
                and sort_field in df.columns
                and pd.api.types.is_numeric_dtype(df[sort_field])
            ):
                model_metric = (
                    df.groupby("model")[sort_field]
                    .mean()
                    .dropna()
                    .sort_values(ascending=ascending)
                )
                if not model_metric.empty:
                    model_order = model_metric.index.tolist()
                    # Append any models missing from the metric (e.g., all NaNs)
                    remaining_models = [
                        model for model in model_values if model not in model_order
                    ]
                    model_order.extend(remaining_models)

            if "model" in df.columns and not df.empty:
                model_summary = (
                    df.groupby("model")
                    .agg(
                        avg_input_tokens=("input_tokens", "mean"),
                        avg_total_duration_ms=("measured_duration_ms", "mean"),
                        avg_tokens_per_second=("tokens_per_second", "mean"),
                        runs=("model", "count"),
                        params_b=("model_params_b", "mean"),
                    )
                    .reset_index()
                )
                model_summary["avg_total_duration_sec"] = (
                    model_summary["avg_total_duration_ms"] / 1000
                )
                default_param_scale = (
                    model_summary["params_b"].median()
                    if not model_summary["params_b"].dropna().empty
                    else 1.0
                )
                model_summary["params_b"].fillna(default_param_scale, inplace=True)
                model_summary["bubble_size"] = model_summary["params_b"] * 60
            else:
                model_summary = pd.DataFrame()

            # Set up tabs for different visualizations
            tab1, tab2, tab3, tab4 = st.tabs(
                [
                    "Performance Metrics",
                    "Token Usage",
                    "Prompt Analysis",
                    "Device Performance",
                ]
            )

            with tab1:
                col1, col2 = st.columns(2)

                with col1:
                    # Generation speed by model
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.barplot(
                        data=df,
                        x="model",
                        y="tokens_per_second",
                        order=model_order or None,
                        ax=ax,
                    )
                    plt.title("Generation Speed by Model")
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Tokens per Second")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

                with col2:
                    # Total duration by model
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.barplot(
                        data=df,
                        x="model",
                        y="measured_duration_ms",
                        order=model_order or None,
                        ax=ax,
                    )
                    plt.title("Total Processing Time by Model")
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Duration (ms)")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

                st.subheader("Input Tokens vs Total Duration (Average)")
                if not model_summary.empty:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.scatter(
                        model_summary["avg_input_tokens"],
                        model_summary["avg_total_duration_sec"],
                        s=model_summary["bubble_size"],
                        alpha=0.7,
                        color="#1f77b4",
                        edgecolors="black",
                    )
                    for _, row in model_summary.iterrows():
                        ax.text(
                            row["avg_input_tokens"],
                            row["avg_total_duration_sec"],
                            row["model"],
                            fontsize=9,
                            ha="left",
                            va="bottom",
                            alpha=0.9,
                        )
                    ax.set_xlabel("Average Input Tokens")
                    ax.set_ylabel("Average Total Duration (s)")
                    ax.grid(True, linestyle="--", alpha=0.6)
                    st.pyplot(fig)
                else:
                    st.info("Not enough data to render the bubble chart.")

                st.subheader("Performance Distributions")
                dist_col1, dist_col2 = st.columns(2)

                with dist_col1:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.violinplot(
                        data=df,
                        x="model",
                        y="tokens_per_second",
                        order=model_order or None,
                        inner="quartile",
                        ax=ax,
                    )
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Tokens per Second")
                    plt.title("Tokens per Second Distribution by Model")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

                with dist_col2:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.violinplot(
                        data=df,
                        x="model",
                        y="total_duration_sec",
                        order=model_order or None,
                        inner="quartile",
                        ax=ax,
                    )
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Total Duration (s)")
                    plt.title("Total Duration Distribution by Model")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

            with tab2:
                col1, col2 = st.columns(2)

                with col1:
                    # Input vs Output tokens
                    df_melted = pd.melt(
                        df,
                        id_vars=["model"],
                        value_vars=["input_tokens", "output_tokens"],
                        var_name="Token Type",
                        value_name="Token Count",
                    )
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.barplot(
                        data=df_melted,
                        x="model",
                        y="Token Count",
                        order=model_order or None,
                        hue="Token Type",
                        ax=ax,
                    )
                    plt.title("Input vs Output Tokens by Model")
                    plt.xticks(rotation=45, ha="right")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

                with col2:
                    # Input processing time vs Output generation time
                    df_melted = pd.melt(
                        df,
                        id_vars=["model"],
                        value_vars=["input_duration_ms", "output_duration_ms"],
                        var_name="Processing Stage",
                        value_name="Duration (ms)",
                    )
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.barplot(
                        data=df_melted,
                        x="model",
                        y="Duration (ms)",
                        order=model_order or None,
                        hue="Processing Stage",
                        ax=ax,
                    )
                    plt.title("Processing Time Breakdown by Model")
                    plt.xticks(rotation=45, ha="right")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

            with tab3:
                col1, col2 = st.columns(2)

                with col1:
                    # Prompt type distribution
                    fig, ax = plt.subplots(figsize=(10, 6))
                    prompt_counts = (
                        df["system_prompt_type"].value_counts().reset_index()
                    )
                    prompt_counts.columns = ["prompt_type", "count"]
                    sns.barplot(data=prompt_counts, x="prompt_type", y="count", ax=ax)
                    plt.title("Prompt Type Distribution")
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Count")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

                with col2:
                    # Performance by prompt type
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.boxplot(
                        data=df,
                        x="system_prompt_type",
                        y="tokens_per_second",
                        ax=ax,
                    )
                    plt.title("Performance by Prompt Type")
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Tokens per Second")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)

                st.subheader("Document Coverage by Model")
                doc_counts = df.assign(
                    document_label=df["document_name"].apply(
                        lambda name: (
                            textwrap.shorten(name, width=55, placeholder="…")
                            if isinstance(name, str)
                            else name
                        )
                    ),
                    _count=1,
                ).pivot_table(
                    index="document_label",
                    columns="model",
                    values="_count",
                    aggfunc="sum",
                    fill_value=0,
                )
                if not doc_counts.empty:
                    if model_order:
                        ordered_cols = [
                            col for col in model_order if col in doc_counts.columns
                        ]
                        remaining_cols = [
                            col for col in doc_counts.columns if col not in ordered_cols
                        ]
                        doc_counts = doc_counts[ordered_cols + remaining_cols]
                    doc_totals = doc_counts.sum(axis=1).sort_values(ascending=False)
                    max_docs = 25
                    if len(doc_totals) > max_docs:
                        doc_counts = doc_counts.loc[doc_totals.index[:max_docs]]
                        st.caption(
                            f"Showing top {max_docs} documents by experiment count."
                        )
                    fig, ax = plt.subplots(figsize=(12, max(6, 0.4 * len(doc_counts))))
                    sns.heatmap(
                        doc_counts,
                        annot=True,
                        fmt="d",
                        cmap="YlGnBu",
                        linewidths=0.3,
                        linecolor="white",
                        cbar=True,
                        ax=ax,
                    )
                    plt.xlabel("Model")
                    plt.ylabel("Document")
                    plt.xticks(rotation=45, ha="right")
                    plt.yticks(rotation=0)
                    plt.title("Experiment Coverage per Document and Model")
                    st.pyplot(fig)
                else:
                    st.info(
                        "Document coverage heatmap is unavailable with the current selection."
                    )

            with tab4:
                # Device performance analysis
                st.subheader("Performance by Device")
                if "device" in df.columns and not df.empty:
                    # Performance by device (all models combined)
                    col1, col2 = st.columns(2)

                    with col1:
                        fig, ax = plt.subplots(figsize=(10, 6))
                        sns.boxplot(data=df, x="device", y="tokens_per_second", ax=ax)
                        plt.title("Tokens per Second by Device")
                        plt.ylabel("Tokens per Second")
                        plt.grid(axis="y", linestyle="--", alpha=0.7)
                        st.pyplot(fig)

                    with col2:
                        fig, ax = plt.subplots(figsize=(10, 6))
                        sns.boxplot(data=df, x="device", y="total_duration_sec", ax=ax)
                        plt.title("Total Duration by Device")
                        plt.ylabel("Duration (seconds)")
                        plt.grid(axis="y", linestyle="--", alpha=0.7)
                        st.pyplot(fig)

                    # Model performance by device
                    st.subheader("Model Performance by Device")
                    fig, ax = plt.subplots(figsize=(12, 8))
                    sns.barplot(
                        data=df,
                        x="model",
                        y="tokens_per_second",
                        hue="device",
                        order=model_order or None,
                        ax=ax,
                    )
                    plt.title("Tokens per Second by Model and Device")
                    plt.xticks(rotation=45, ha="right")
                    plt.ylabel("Tokens per Second")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    plt.legend(title="Device")
                    st.pyplot(fig)

                    # Device usage count
                    st.subheader("Device Usage Distribution")
                    device_counts = df["device"].value_counts().reset_index()
                    device_counts.columns = ["device", "count"]
                    fig, ax = plt.subplots(figsize=(8, 5))
                    sns.barplot(data=device_counts, x="device", y="count", ax=ax)
                    plt.title("Number of Experiments by Device")
                    plt.ylabel("Count")
                    plt.grid(axis="y", linestyle="--", alpha=0.7)
                    st.pyplot(fig)
                else:
                    st.info(
                        "Device performance data is unavailable with the current selection."
                    )

    else:
        st.info("No results match the selected filters.")

    # Add footer with instructions
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Instructions")
    st.sidebar.markdown(
        """
        1. Use the filters above to narrow down results:
           - Filter by model, prompt type, document, or device (CPU/CUDA)
           - Use multiple selections in the Models filter
        2. Expand result items to view details
        3. Toggle display options to show/hide metrics and raw responses
        4. Explore visualization tabs:
           - Performance Metrics: Compare speed and duration between models
           - Token Usage: Analyze input and output token distributions
           - Prompt Analysis: Review prompt type performance
           - Device Performance: Compare CPU vs CUDA performance
        5. Sort results by any metric including device type
        """
    )


if __name__ == "__main__":
    main()
