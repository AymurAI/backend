from spacy.language import Language
from spacy.pipeline import EntityRuler

from .entity_custom import EntityCustom
from .entity_ruler import fetch_ruler_patterns_by_tag
from .entity_matcher import (
    EntityMatcher,
    ArticlesMatcher,
    ViolenceContextMatcher,
    fetch_cb_by_tag,
    matcher_patterns,
)

violence_context_matcher = ViolenceContextMatcher()
violence_context_patterns = violence_context_matcher.get_violence_context_patterns()
VIOLENCE_CONTEXT_LABEL_MAPPING = {
    "CONTEXTO_VIOLENCIA_DE_GÉNERO": "GENDER_VIOLENCE_CONTEXT",
    "CONTEXTO_VIOLENCIA": "VIOLENCE_CONTEXT_TYPE",
}
VIOLENCE_CONTEXT_PATTERNS = [
    (VIOLENCE_CONTEXT_LABEL_MAPPING[label], pattern)
    for (label, pattern) in violence_context_patterns
]


@Language.factory(name="ia2_entity_ruler")
def ia2_entity_ruler(nlp, name):
    return EntityRuler(nlp)


@Language.factory(name="ia2_entity_matcher")
def ia2_entity_matcher(nlp, name):
    return EntityMatcher(
        nlp,
        matcher_patterns,
        after_callbacks=[cb(nlp) for cb in fetch_cb_by_tag("todas")],
    )


@Language.factory(name="ia2_entity_custom")
def ia2_entity_custom(nlp, name):
    return EntityCustom(nlp, "todas")


@Language.factory(name="ia2_violence_context_ruler")
def ia2_violence_context(nlp, name, overwrite_ents: bool = True):
    ruler = EntityRuler(
        nlp,
        patterns=VIOLENCE_CONTEXT_PATTERNS,
        overwrite_ents=overwrite_ents,
    )
    return ruler
