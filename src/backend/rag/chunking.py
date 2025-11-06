"""
Chunking Strategies Module
Implements three different chunking strategies:
1. Heuristic Chunking - Based on word count and logical structures
2. Semantic Chunking - Based on headers and semantic elements
3. Intelligent Chunking - Using LLM for smart chunking
"""

import re
import logging
from typing import List, Dict, Any
from abc import ABC, abstractmethod
import litellm
from ..config import settings

logger = logging.getLogger(__name__)


class Chunk:
    """Represents a text chunk with metadata"""
    
    def __init__(self, text: str, metadata: Dict[str, Any] = None):
        self.text = text
        self.metadata = metadata or {}
        self.word_count = len(text.split())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "metadata": self.metadata,
            "word_count": self.word_count
        }


class BaseChunker(ABC):
    """Abstract base class for chunking strategies"""
    
    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    @abstractmethod
    async def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """Chunk the text into smaller pieces"""
        pass


class HeuristicChunker(BaseChunker):
    """
    Heuristic Chunking Strategy
    Chunks based on word count, breaking at nearest logical structure (sentence, paragraph)
    """
    
    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        super().__init__(chunk_size, overlap)
    
    async def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Chunk text using heuristic approach
        - Target chunk_size words
        - Break at paragraph boundaries when possible
        - Fall back to sentence boundaries
        - Maintain overlap between chunks
        """
        logger.info(f"Heuristic chunking with size={self.chunk_size}, overlap={self.overlap}")
        
        # Split into paragraphs first
        paragraphs = self._split_into_paragraphs(text)
        
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for para in paragraphs:
            para_word_count = len(para.split())
            
            # If adding this paragraph exceeds chunk size
            if current_word_count + para_word_count > self.chunk_size:
                if current_chunk:
                    # Create chunk from accumulated paragraphs
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(Chunk(
                        text=chunk_text,
                        metadata={
                            **(metadata or {}),
                            "chunk_index": len(chunks),
                            "chunking_strategy": "heuristic",
                            "paragraph_count": len(current_chunk)
                        }
                    ))
                    
                    # Handle overlap
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = [overlap_text] if overlap_text else []
                    current_word_count = len(overlap_text.split()) if overlap_text else 0
                
                # If single paragraph is too large, split by sentences
                if para_word_count > self.chunk_size:
                    sentence_chunks = self._chunk_by_sentences(para, metadata, len(chunks))
                    chunks.extend(sentence_chunks)
                else:
                    current_chunk.append(para)
                    current_word_count += para_word_count
            else:
                current_chunk.append(para)
                current_word_count += para_word_count
        
        # Add remaining content
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(Chunk(
                text=chunk_text,
                metadata={
                    **(metadata or {}),
                    "chunk_index": len(chunks),
                    "chunking_strategy": "heuristic",
                    "paragraph_count": len(current_chunk)
                }
            ))
        
        logger.info(f"Created {len(chunks)} chunks using heuristic strategy")
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split by double newline or more
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _chunk_by_sentences(self, text: str, metadata: Dict[str, Any], start_index: int) -> List[Chunk]:
        """Chunk large paragraph by sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = []
        current_words = 0
        
        for sentence in sentences:
            sentence_words = len(sentence.split())
            
            if current_words + sentence_words > self.chunk_size and current:
                chunk_text = " ".join(current)
                chunks.append(Chunk(
                    text=chunk_text,
                    metadata={
                        **(metadata or {}),
                        "chunk_index": start_index + len(chunks),
                        "chunking_strategy": "heuristic_sentence",
                        "sentence_count": len(current)
                    }
                ))
                
                # Overlap: keep last sentence
                if self.overlap > 0 and current:
                    overlap_sentences = []
                    overlap_words = 0
                    for s in reversed(current):
                        s_words = len(s.split())
                        if overlap_words + s_words <= self.overlap:
                            overlap_sentences.insert(0, s)
                            overlap_words += s_words
                        else:
                            break
                    current = overlap_sentences
                    current_words = overlap_words
                else:
                    current = []
                    current_words = 0
            
            current.append(sentence)
            current_words += sentence_words
        
        if current:
            chunk_text = " ".join(current)
            chunks.append(Chunk(
                text=chunk_text,
                metadata={
                    **(metadata or {}),
                    "chunk_index": start_index + len(chunks),
                    "chunking_strategy": "heuristic_sentence",
                    "sentence_count": len(current)
                }
            ))
        
        return chunks
    
    def _get_overlap_text(self, paragraphs: List[str]) -> str:
        """Get overlap text from end of current chunk"""
        if not paragraphs or self.overlap <= 0:
            return ""
        
        # Take last paragraph(s) that fit in overlap
        overlap_paras = []
        word_count = 0
        
        for para in reversed(paragraphs):
            para_words = len(para.split())
            if word_count + para_words <= self.overlap:
                overlap_paras.insert(0, para)
                word_count += para_words
            else:
                break
        
        return "\n\n".join(overlap_paras) if overlap_paras else ""


class SemanticChunker(BaseChunker):
    """
    Semantic Chunking Strategy
    Chunks based on markdown headers and semantic structure
    """
    
    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        super().__init__(chunk_size, overlap)
    
    async def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Chunk text using semantic structure
        - Use markdown headers as primary boundaries
        - Keep related content together
        - Maintain hierarchy
        """
        logger.info(f"Semantic chunking with size={self.chunk_size}")
        
        sections = self._parse_markdown_sections(text)
        chunks = []
        
        for section in sections:
            section_text = section['text']
            section_word_count = len(section_text.split())
            
            # If section is small enough, keep it as one chunk
            if section_word_count <= self.chunk_size:
                chunks.append(Chunk(
                    text=section_text,
                    metadata={
                        **(metadata or {}),
                        "chunk_index": len(chunks),
                        "chunking_strategy": "semantic",
                        "section_title": section.get('title', ''),
                        "section_level": section.get('level', 0),
                        "is_complete_section": True
                    }
                ))
            else:
                # Section too large, split further using heuristic
                heuristic_chunker = HeuristicChunker(self.chunk_size, self.overlap)
                sub_chunks = await heuristic_chunker.chunk(section_text, {
                    **(metadata or {}),
                    "parent_section": section.get('title', ''),
                    "section_level": section.get('level', 0)
                })
                
                for sub_chunk in sub_chunks:
                    sub_chunk.metadata.update({
                        "chunking_strategy": "semantic_hybrid",
                        "is_complete_section": False
                    })
                    chunks.append(sub_chunk)
        
        logger.info(f"Created {len(chunks)} chunks using semantic strategy")
        return chunks
    
    def _parse_markdown_sections(self, text: str) -> List[Dict[str, Any]]:
        """Parse markdown into sections based on headers"""
        lines = text.split('\n')
        sections = []
        current_section = {
            'title': 'Introduction',
            'level': 0,
            'text': []
        }
        
        for line in lines:
            # Check if line is a markdown header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if header_match:
                # Save previous section
                if current_section['text']:
                    current_section['text'] = '\n'.join(current_section['text']).strip()
                    if current_section['text']:
                        sections.append(current_section)
                
                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_section = {
                    'title': title,
                    'level': level,
                    'text': [line]  # Include header in text
                }
            else:
                current_section['text'].append(line)
        
        # Add last section
        if current_section['text']:
            current_section['text'] = '\n'.join(current_section['text']).strip()
            if current_section['text']:
                sections.append(current_section)
        
        return sections


class IntelligentChunker(BaseChunker):
    """
    Intelligent Chunking Strategy
    Uses LLM to determine optimal chunk boundaries
    """
    
    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        super().__init__(chunk_size, overlap)
        self.llm_model = settings.LLM_MODEL
    
    async def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Chunk text using LLM intelligence
        - Analyze content for natural boundaries
        - Maintain semantic coherence
        - Consider context and topic shifts
        """
        logger.info(f"Intelligent chunking with LLM model={self.llm_model}")
        
        # For very short text, return as single chunk
        word_count = len(text.split())
        if word_count <= self.chunk_size:
            return [Chunk(
                text=text,
                metadata={
                    **(metadata or {}),
                    "chunk_index": 0,
                    "chunking_strategy": "intelligent_single"
                }
            )]
        
        # First, use semantic chunking as base
        semantic_chunker = SemanticChunker(self.chunk_size, self.overlap)
        base_chunks = await semantic_chunker.chunk(text, metadata)
        
        # Use LLM to refine boundaries for large chunks
        refined_chunks = []
        
        for i, chunk in enumerate(base_chunks):
            if chunk.word_count > self.chunk_size * 1.5:
                # Chunk is too large, ask LLM to split it
                sub_chunks = await self._llm_split_chunk(chunk.text, metadata, i)
                refined_chunks.extend(sub_chunks)
            else:
                # Update metadata
                chunk.metadata.update({
                    "chunking_strategy": "intelligent",
                    "chunk_index": len(refined_chunks)
                })
                refined_chunks.append(chunk)
        
        logger.info(f"Created {len(refined_chunks)} chunks using intelligent strategy")
        return refined_chunks
    
    async def _llm_split_chunk(self, text: str, metadata: Dict[str, Any], base_index: int) -> List[Chunk]:
        """Use LLM to intelligently split a large chunk"""
        try:
            prompt = f"""Analyze the following text and identify the best places to split it into smaller chunks of approximately {self.chunk_size} words each.

Each chunk should:
1. Be semantically coherent (complete thoughts/topics)
2. Start and end at natural boundaries
3. Be around {self.chunk_size} words (but prioritize coherence)

Text to split:
{text}

Respond with the split points marked by "---SPLIT---" between sections. Include the original text with split markers."""

            response = await litellm.acompletion(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=len(text.split()) + 200
            )
            
            split_text = response.choices[0].message.content
            
            # Parse LLM response to extract chunks
            sections = split_text.split("---SPLIT---")
            chunks = []
            
            for i, section in enumerate(sections):
                section = section.strip()
                if section and len(section.split()) > 50:  # Minimum chunk size
                    chunks.append(Chunk(
                        text=section,
                        metadata={
                            **(metadata or {}),
                            "chunk_index": base_index * 10 + i,  # Preserve ordering
                            "chunking_strategy": "intelligent_llm",
                            "llm_model": self.llm_model
                        }
                    ))
            
            return chunks if chunks else [Chunk(text=text, metadata=metadata)]
        
        except Exception as e:
            logger.warning(f"LLM chunking failed, falling back to heuristic: {str(e)}")
            # Fallback to heuristic chunking
            heuristic_chunker = HeuristicChunker(self.chunk_size, self.overlap)
            return await heuristic_chunker.chunk(text, metadata)


def get_chunker(strategy: str = "semantic", chunk_size: int = 800, overlap: int = 150) -> BaseChunker:
    """Factory function to get appropriate chunker"""
    if strategy == "heuristic":
        return HeuristicChunker(chunk_size, overlap)
    elif strategy == "semantic":
        return SemanticChunker(chunk_size, overlap)
    elif strategy == "intelligent":
        return IntelligentChunker(chunk_size, overlap)
    else:
        logger.warning(f"Unknown strategy '{strategy}', defaulting to semantic")
        return SemanticChunker(chunk_size, overlap)

