"""
Vectorization Service for TMWS
Handles text embedding generation using sentence-transformers
"""

import logging
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer

from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorizationService:
    """Service for generating text embeddings."""
    
    _model = None
    _model_name = None
    
    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """Get or initialize the sentence transformer model."""
        current_model = settings.embedding_model
        
        if cls._model is None or cls._model_name != current_model:
            logger.info(f"Loading embedding model: {current_model}")
            cls._model = SentenceTransformer(current_model)
            cls._model_name = current_model
            logger.info(f"Model loaded successfully: {current_model}")
        
        return cls._model
    
    async def vectorize_text(
        self, 
        text: Union[str, List[str]]
    ) -> np.ndarray:
        """
        Generate vector embedding for text.
        
        Args:
            text: Single string or list of strings to vectorize
            
        Returns:
            Numpy array of embeddings
        """
        model = self.get_model()
        
        # Convert single string to list for consistent processing
        if isinstance(text, str):
            texts = [text]
            single_input = True
        else:
            texts = text
            single_input = False
        
        # Generate embeddings
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=settings.max_embedding_batch_size
        )
        
        # Return single embedding if single input
        if single_input:
            return embeddings[0]
        
        return embeddings
    
    async def vectorize_batch(
        self,
        texts: List[str],
        batch_size: int = None
    ) -> List[np.ndarray]:
        """
        Generate vector embeddings for a batch of texts.
        
        Args:
            texts: List of texts to vectorize
            batch_size: Batch size for processing (uses config default if None)
            
        Returns:
            List of numpy arrays
        """
        if not texts:
            return []
        
        batch_size = batch_size or settings.max_embedding_batch_size
        model = self.get_model()
        
        # Process in batches for memory efficiency
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = model.encode(
                batch,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            all_embeddings.extend(embeddings)
        
        logger.info(f"Vectorized {len(texts)} texts in batches of {batch_size}")
        
        return all_embeddings
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        model = self.get_model()
        return model.get_sentence_embedding_dimension()
    
    async def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0 to 1)
        """
        # Normalize vectors
        norm1 = embedding1 / np.linalg.norm(embedding1)
        norm2 = embedding2 / np.linalg.norm(embedding2)
        
        # Compute cosine similarity
        similarity = np.dot(norm1, norm2)
        
        # Ensure result is between 0 and 1
        return float(max(0, min(1, similarity)))
    
    async def find_most_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[np.ndarray],
        top_k: int = 10,
        min_similarity: float = 0.0
    ) -> List[tuple[int, float]]:
        """
        Find the most similar embeddings from a list of candidates.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        if not candidate_embeddings:
            return []
        
        # Compute similarities
        similarities = []
        for i, candidate in enumerate(candidate_embeddings):
            similarity = await self.compute_similarity(query_embedding, candidate)
            if similarity >= min_similarity:
                similarities.append((i, similarity))
        
        # Sort by similarity (descending) and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]