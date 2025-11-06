"""
Vector Store Management Module
Supports Pinecone and Weaviate for vector storage and retrieval
"""

import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import litellm
from pinecone import Pinecone, ServerlessSpec
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from ..config import settings

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector stores"""
    
    @abstractmethod
    async def create_index(self, index_name: str, dimension: int):
        """Create a new index"""
        pass
    
    @abstractmethod
    async def upsert_vectors(self, vectors: List[Dict[str, Any]], namespace: str):
        """Upsert vectors to the store"""
        pass
    
    @abstractmethod
    async def query(self, query_vector: List[float], namespace: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query similar vectors"""
        pass
    
    @abstractmethod
    async def delete_namespace(self, namespace: str):
        """Delete all vectors in a namespace"""
        pass


class PineconeVectorStore(VectorStore):
    """Pinecone vector database implementation"""
    
    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.index_name = settings.PINECONE_INDEX_NAME
        
        if not self.api_key:
            raise ValueError("PINECONE_API_KEY not set in configuration")
        
        self.pc = Pinecone(api_key=self.api_key)
        self.index = None
        
        logger.info(f"Initialized Pinecone vector store with index: {self.index_name}")
    
    async def create_index(self, index_name: str = None, dimension: int = 1536):
        """Create Pinecone index with serverless spec"""
        index_name = index_name or self.index_name
        
        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if index_name not in existing_indexes:
                logger.info(f"Creating Pinecone serverless index: {index_name}")
                self.pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"  # Default serverless region
                    )
                )
                logger.info(f"Pinecone index '{index_name}' created successfully")
            else:
                logger.info(f"Pinecone index '{index_name}' already exists")
            
            self.index = self.pc.Index(index_name)
        
        except Exception as e:
            logger.error(f"Error creating Pinecone index: {str(e)}")
            raise
    
    async def upsert_vectors(self, vectors: List[Dict[str, Any]], namespace: str):
        """Upsert vectors to Pinecone"""
        if not self.index:
            await self.create_index()
        
        try:
            # Prepare vectors for Pinecone
            pinecone_vectors = []
            for vec in vectors:
                pinecone_vectors.append({
                    "id": vec["id"],
                    "values": vec["vector"],
                    "metadata": vec["metadata"]
                })
            
            # Upsert in batches
            batch_size = 100
            for i in range(0, len(pinecone_vectors), batch_size):
                batch = pinecone_vectors[i:i+batch_size]
                self.index.upsert(vectors=batch, namespace=namespace)
            
            logger.info(f"Upserted {len(vectors)} vectors to namespace '{namespace}'")
        
        except Exception as e:
            logger.error(f"Error upserting vectors to Pinecone: {str(e)}")
            raise
    
    async def query(self, query_vector: List[float], namespace: str, top_k: int = 5, 
                   filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Query Pinecone for similar vectors"""
        if not self.index:
            await self.create_index()
        
        try:
            results = self.index.query(
                vector=query_vector,
                namespace=namespace,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
            
            # Format results
            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                })
            
            return formatted_results
        
        except Exception as e:
            logger.error(f"Error querying Pinecone: {str(e)}")
            raise
    
    async def delete_namespace(self, namespace: str):
        """Delete namespace from Pinecone"""
        if not self.index:
            await self.create_index()
        
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted namespace '{namespace}' from Pinecone")
        
        except Exception as e:
            logger.error(f"Error deleting namespace: {str(e)}")
            raise


class WeaviateVectorStore(VectorStore):
    """Weaviate vector database implementation"""
    
    def __init__(self):
        self.url = settings.WEAVIATE_URL
        self.api_key = settings.WEAVIATE_API_KEY
        self.collection_name = "ChemBotContent"
        
        # Connect to Weaviate
        if self.api_key:
            self.client = weaviate.connect_to_wcs(
                cluster_url=self.url,
                auth_credentials=weaviate.auth.AuthApiKey(self.api_key)
            )
        else:
            self.client = weaviate.connect_to_local(host=self.url.replace("http://", ""))
        
        logger.info(f"Initialized Weaviate vector store at: {self.url}")
    
    async def create_index(self, index_name: str = None, dimension: int = 1536):
        """Create Weaviate collection"""
        collection_name = index_name or self.collection_name
        
        try:
            # Check if collection exists
            if not self.client.collections.exists(collection_name):
                logger.info(f"Creating Weaviate collection: {collection_name}")
                
                self.client.collections.create(
                    name=collection_name,
                    properties=[
                        Property(name="text", data_type=DataType.TEXT),
                        Property(name="content_id", data_type=DataType.TEXT),
                        Property(name="chunk_index", data_type=DataType.INT),
                        Property(name="metadata", data_type=DataType.OBJECT),
                    ],
                    vectorizer_config=Configure.Vectorizer.none()  # We provide vectors
                )
                
                logger.info(f"Weaviate collection '{collection_name}' created")
            else:
                logger.info(f"Weaviate collection '{collection_name}' already exists")
        
        except Exception as e:
            logger.error(f"Error creating Weaviate collection: {str(e)}")
            raise
    
    async def upsert_vectors(self, vectors: List[Dict[str, Any]], namespace: str):
        """Upsert vectors to Weaviate"""
        try:
            collection = self.client.collections.get(self.collection_name)
            
            # Prepare objects for Weaviate
            for vec in vectors:
                data_object = {
                    "text": vec["metadata"].get("text", ""),
                    "content_id": namespace,  # Use namespace as content_id
                    "chunk_index": vec["metadata"].get("chunk_index", 0),
                    "metadata": vec["metadata"]
                }
                
                collection.data.insert(
                    properties=data_object,
                    vector=vec["vector"],
                    uuid=vec["id"]
                )
            
            logger.info(f"Upserted {len(vectors)} vectors to Weaviate")
        
        except Exception as e:
            logger.error(f"Error upserting vectors to Weaviate: {str(e)}")
            raise
    
    async def query(self, query_vector: List[float], namespace: str, top_k: int = 5,
                   filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Query Weaviate for similar vectors"""
        try:
            collection = self.client.collections.get(self.collection_name)
            
            # Build filter
            where_filter = None
            if namespace:
                where_filter = {
                    "path": ["content_id"],
                    "operator": "Equal",
                    "valueText": namespace
                }
            
            # Query
            response = collection.query.near_vector(
                near_vector=query_vector,
                limit=top_k,
                where=where_filter,
                return_properties=["text", "content_id", "chunk_index", "metadata"]
            )
            
            # Format results
            formatted_results = []
            for obj in response.objects:
                formatted_results.append({
                    "id": str(obj.uuid),
                    "score": obj.metadata.distance if hasattr(obj.metadata, 'distance') else 1.0,
                    "metadata": {
                        "text": obj.properties.get("text", ""),
                        "content_id": obj.properties.get("content_id", ""),
                        "chunk_index": obj.properties.get("chunk_index", 0),
                        **obj.properties.get("metadata", {})
                    }
                })
            
            return formatted_results
        
        except Exception as e:
            logger.error(f"Error querying Weaviate: {str(e)}")
            raise
    
    async def delete_namespace(self, namespace: str):
        """Delete content by namespace in Weaviate"""
        try:
            collection = self.client.collections.get(self.collection_name)
            
            collection.data.delete_many(
                where={
                    "path": ["content_id"],
                    "operator": "Equal",
                    "valueText": namespace
                }
            )
            
            logger.info(f"Deleted namespace '{namespace}' from Weaviate")
        
        except Exception as e:
            logger.error(f"Error deleting namespace: {str(e)}")
            raise


class VectorStoreManager:
    """Manager class for vector store operations with embedding generation"""
    
    def __init__(self, provider: str = None):
        self.provider = provider or settings.VECTOR_DB_PROVIDER
        self.embedding_model = settings.EMBEDDING_MODEL
        self.embedding_dimension = settings.EMBEDDING_DIMENSION
        
        # Initialize vector store
        if self.provider == "pinecone":
            self.store = PineconeVectorStore()
        elif self.provider == "weaviate":
            self.store = WeaviateVectorStore()
        else:
            raise ValueError(f"Unsupported vector store provider: {self.provider}")
        
        logger.info(f"Initialized VectorStoreManager with provider: {self.provider}")
    
    async def initialize(self):
        """Initialize vector store (create index/collection)"""
        await self.store.create_index(dimension=self.embedding_dimension)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using LiteLLM"""
        try:
            response = await litellm.aembedding(
                model=self.embedding_model,
                input=text
            )
            return response.data[0]["embedding"]
        
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    async def store_chunks(self, chunks: List[Any], content_id: str):
        """Generate embeddings and store chunks"""
        vectors = []
        
        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = await self.generate_embedding(chunk.text)
            
            # Prepare vector
            vectors.append({
                "id": f"{content_id}_chunk_{i}",
                "vector": embedding,
                "metadata": {
                    "text": chunk.text,
                    "content_id": content_id,
                    **chunk.metadata
                }
            })
        
        # Store in vector database
        await self.store.upsert_vectors(vectors, namespace=content_id)
        
        logger.info(f"Stored {len(chunks)} chunks for content {content_id}")
        return len(chunks)
    
    async def search_similar(self, query: str, content_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks"""
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        
        # Query vector store
        results = await self.store.query(
            query_vector=query_embedding,
            namespace=content_id,
            top_k=top_k
        )
        
        return results
    
    async def delete_content(self, content_id: str):
        """Delete all chunks for a content"""
        await self.store.delete_namespace(content_id)
        logger.info(f"Deleted all chunks for content {content_id}")

