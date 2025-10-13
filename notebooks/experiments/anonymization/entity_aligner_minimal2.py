"""
Minimal Entity Aligner - Crea formato langextract desde datos NER
"""

import difflib
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class AlignmentStatus(Enum):
    MATCH_EXACT = "match_exact"
    MATCH_FUZZY = "match_fuzzy"
    NO_MATCH = None


@dataclass
class CharInterval:
    start_pos: int
    end_pos: int


@dataclass
class Extraction:
    extraction_class: str
    extraction_text: str
    char_interval: CharInterval
    alignment_status: AlignmentStatus
    extraction_index: int
    group_index: int
    description: Optional[str] = None
    attributes: Dict[str, Any] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class AnnotatedDocument:
    document_id: str
    text: str
    extractions: List[Extraction]


class EntityAligner:
    """Alineador minimalista para crear formato langextract"""
    
    def __init__(self, fuzzy_threshold: float = 0.75):
        self.fuzzy_threshold = fuzzy_threshold
    
    def _normalize_text(self, text: str) -> str:
        """Normalizar texto para comparación flexible"""
        return re.sub(r'[.,;:!?]+$', '', re.sub(r'\s+', ' ', text.strip().lower()))
    
    def _texts_match(self, text1: str, text2: str) -> bool:
        """Comparar textos de forma flexible"""
        return self._normalize_text(text1) == self._normalize_text(text2)
    
    def _find_entity_in_text(self, entity_text: str, source_text: str, 
                            start_search: int = 0) -> Optional[Dict[str, Any]]:
        """Buscar entidad en texto"""
        # Match exacto
        exact_pos = source_text.find(entity_text, start_search)
        if exact_pos != -1:
            return {
                'start_char': exact_pos,
                'end_char': exact_pos + len(entity_text),
                'status': AlignmentStatus.MATCH_EXACT,
                'score': 1.0
            }
        
        # Match normalizado (ignora mayúsculas/puntuación)
        for i in range(start_search, len(source_text) - len(entity_text) + 1):
            window_text = source_text[i:i + len(entity_text)]
            if self._texts_match(window_text, entity_text):
                return {
                    'start_char': i,
                    'end_char': i + len(entity_text),
                    'status': AlignmentStatus.MATCH_EXACT,
                    'score': 1.0
                }
        
        # Match con ventana flexible
        for window_size in range(len(entity_text) - 2, len(entity_text) + 3):
            if window_size <= 0 or window_size > len(source_text):
                continue
            for i in range(start_search, len(source_text) - window_size + 1):
                window_text = source_text[i:i + window_size]
                if self._texts_match(window_text, entity_text):
                    return {
                        'start_char': i,
                        'end_char': i + window_size,
                        'status': AlignmentStatus.MATCH_EXACT,
                        'score': 1.0
                    }
        
        # Match fuzzy
        window_size = len(entity_text)
        best_match = None
        best_score = 0.0
        
        for i in range(start_search, len(source_text) - window_size + 1):
            window_text = source_text[i:i + window_size]
            window_normalized = self._normalize_text(window_text)
            entity_normalized = self._normalize_text(entity_text)
            
            matcher = difflib.SequenceMatcher(None, entity_normalized, window_normalized)
            ratio = matcher.ratio()
            
            if ratio >= self.fuzzy_threshold and ratio > best_score:
                best_score = ratio
                best_match = {
                    'start_char': i,
                    'end_char': i + window_size,
                    'status': AlignmentStatus.MATCH_FUZZY,
                    'score': ratio
                }
        
        return best_match
    
    def _find_all_occurrences(self, entity_text: str, source_text: str) -> List[Dict[str, Any]]:
        """Encontrar todas las ocurrencias de una entidad"""
        occurrences = []
        start_search = 0
        
        while True:
            match = self._find_entity_in_text(entity_text, source_text, start_search)
            if not match:
                break
            occurrences.append(match)
            start_search = match['end_char']
        
        return occurrences
    
    def align_entities(self, entities: List[Dict[str, Any]], 
                      source_text: str) -> AnnotatedDocument:
        """Alinear entidades y crear AnnotatedDocument"""
        extractions = []
        extraction_index = 1
        
        for entity in entities:
            entity_text = entity.get('attrs', {}).get('aymurai_alt_text', '')
            entity_class = entity.get('attrs', {}).get('aymurai_label', '')
            entity_attrs = entity.get('attrs', {}).get('aymurai_label_subclass', {})
            
            occurrences = self._find_all_occurrences(entity_text, source_text)
            
            if not occurrences:
                extraction = Extraction(
                    extraction_class=entity_class,
                    extraction_text=entity_text,
                    char_interval=CharInterval(start_pos=0, end_pos=0),
                    alignment_status=AlignmentStatus.NO_MATCH,
                    extraction_index=extraction_index,
                    group_index=0,
                    description=None,
                    attributes=entity_attrs
                )
                extractions.append(extraction)
                extraction_index += 1
            else:
                for i, occurrence in enumerate(occurrences):
                    extraction = Extraction(
                        extraction_class=entity_class,
                        extraction_text=entity_text,
                        char_interval=CharInterval(
                            start_pos=occurrence['start_char'],
                            end_pos=occurrence['end_char']
                        ),
                        alignment_status=occurrence['status'],
                        extraction_index=extraction_index,
                        group_index=i,
                        description=None,
                        attributes=entity_attrs
                    )
                    extractions.append(extraction)
                    extraction_index += 1
        
        return AnnotatedDocument(
            document_id="legal_document_001",
            text=source_text,
            extractions=extractions
        )

def create_langextract_alignment(ner_data: Dict[str, Any], 
                                fuzzy_threshold: float = 0.75) -> AnnotatedDocument:
    """
    Función principal para crear alineación en formato langextract
    
    Args:
        ner_data: Diccionario con 'document' y 'labels'
        fuzzy_threshold: Umbral para matching fuzzy (0.0-1.0)
    
    Returns:
        AnnotatedDocument en formato langextract
    """
    aligner = EntityAligner(fuzzy_threshold=fuzzy_threshold)
    return aligner.align_entities(ner_data['labels'], ner_data['document'])


def validate_alignment(annotated_doc: AnnotatedDocument) -> Dict[str, Any]:
    """Validar calidad de la alineación"""
    total = len(annotated_doc.extractions)
    exact_matches = sum(1 for ext in annotated_doc.extractions 
                       if ext.alignment_status == AlignmentStatus.MATCH_EXACT)
    fuzzy_matches = sum(1 for ext in annotated_doc.extractions 
                       if ext.alignment_status == AlignmentStatus.MATCH_FUZZY)
    no_matches = sum(1 for ext in annotated_doc.extractions 
                    if ext.alignment_status == AlignmentStatus.NO_MATCH)
    
    # Validar posiciones
    aligner = EntityAligner()
    valid_positions = 0
    for extraction in annotated_doc.extractions:
        start = extraction.char_interval.start_pos
        end = extraction.char_interval.end_pos
        text = annotated_doc.text #annotated_doc.attrs.get('text', '') #
        extraction_text =  extraction.extraction_text #attrs.get('aymurai_alt_text', '')
        if (0 <= start < end <= len(text)):
            actual_text = text[start:end] #annotated_doc.text
            if aligner._texts_match(actual_text,extraction_text): # extraction.extraction_text
                valid_positions += 1
    
    return {
        'total_extractions': total,
        'exact_matches': exact_matches,
        'fuzzy_matches': fuzzy_matches,
        'no_matches': no_matches,
        'valid_positions': valid_positions,
        'alignment_accuracy': valid_positions / total if total > 0 else 0,
        'exact_match_rate': exact_matches / total if total > 0 else 0
    }


# Función de conveniencia para uso directo
def align_ner_data(ner_data: Dict[str, Any], 
                   fuzzy_threshold: float = 0.75,
                   validate: bool = True) -> tuple[AnnotatedDocument, Dict[str, Any]]:
    """
    Función de conveniencia que alinea y valida en un solo paso
    
    Args:
        ner_data: Diccionario con 'document' y 'labels'
        fuzzy_threshold: Umbral para matching fuzzy
        validate: Si validar la alineación
    
    Returns:
        Tupla con (AnnotatedDocument, estadísticas)
    """
    annotated_doc = create_langextract_alignment(ner_data, fuzzy_threshold)
    
    if validate:
        stats = validate_alignment(annotated_doc)
        return annotated_doc, stats
    
    return annotated_doc, {}


if __name__ == "__main__":
    # Ejemplo de uso
    sample_data = {
        'document': 'JUZGADO DE FAMILIA N.o 1 DE LA CIUDAD DE SAN LORENZO',
        'labels': [
            {'attrs': {'label': 'LOC'}, 'text': 'SAN LORENZO'},
            {'attrs': {'label': 'NUM_EXPEDIENTE'}, 'text': '3187/2023'}
        ]
    }
    
    # Usar función de conveniencia
    annotated_doc, stats = align_ner_data(sample_data)
    
    print("AnnotatedDocument creado:")
    print(f"  Total extracciones: {len(annotated_doc.extractions)}")
    print(f"  Precisión: {stats.get('alignment_accuracy', 0):.2%}")
    
    # Mostrar algunas extracciones
    for i, ext in enumerate(annotated_doc.extractions[:3]):
        print(f"  {i+1}. {ext.extraction_class}: '{ext.extraction_text}'")
        print(f"     Posición: {ext.char_interval.start_pos}-{ext.char_interval.end_pos}")
        print(f"     Estado: {ext.alignment_status.value}")
