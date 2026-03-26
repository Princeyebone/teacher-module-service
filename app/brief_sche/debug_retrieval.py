"""Test vector search directly - without generating new embedding"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_vector_search():
    from app.core.database import get_db
    from sqlalchemy import text
    
    output_file = os.path.join(os.path.dirname(__file__), "vector_test_output.txt")
    
    with open(output_file, "w", encoding="utf-8") as f:
        db_gen = get_db()
        db = await anext(db_gen)
        
        try:
            # 1. Get an existing embedding to use as test
            f.write("1. GETTING EXISTING EMBEDDING AS REFERENCE\n")
            f.write("="*60 + "\n")
            
            result0 = await db.execute(
                text("""
                    SELECT ke.embedding, km.pillar, LEFT(ke.chunk_text, 100) as preview
                    FROM knowledgeembedding ke
                    JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                    WHERE LOWER(km.pillar) = 'lesson design'
                    LIMIT 1
                """)
            )
            row0 = result0.fetchone()
            
            if not row0:
                f.write("ERROR: No embeddings found in lesson design pillar!\n")
                
                # Check what pillars have embeddings
                f.write("\nChecking all pillars with embeddings:\n")
                result_check = await db.execute(
                    text("""
                        SELECT km.pillar, COUNT(*) as cnt
                        FROM knowledgeembedding ke
                        JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                        GROUP BY km.pillar
                    """)
                )
                rows_check = result_check.fetchall()
                for row in rows_check:
                    f.write(f"  '{row.pillar}': {row.cnt}\n")
                return
            
            f.write(f"Found reference embedding from pillar: '{row0.pillar}'\n")
            f.write(f"Preview: {row0.preview}...\n")
            
            # Use this embedding as query
            reference_embedding = row0.embedding
            f.write(f"Embedding type: {type(reference_embedding)}\n")
            
            # Convert to string format for query
            if hasattr(reference_embedding, '__iter__'):
                emb_str = "[" + ",".join(str(x) for x in reference_embedding) + "]"
            else:
                emb_str = str(reference_embedding)
            
            f.write(f"Embedding string (first 50 chars): {emb_str[:50]}...\n")
            
            # 2. Use this embedding to search
            f.write("\n2. SEARCHING WITH REFERENCE EMBEDDING\n")
            f.write("="*60 + "\n")
            
            result2 = await db.execute(
                text("""
                    SELECT 
                        ke.id,
                        km.pillar,
                        LEFT(ke.chunk_text, 100) as preview,
                        ke.embedding <=> :query_embedding AS distance
                    FROM knowledgeembedding ke
                    JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                    WHERE LOWER(km.pillar) = 'lesson design'
                    ORDER BY ke.embedding <=> :query_embedding
                    LIMIT 5
                """),
                {"query_embedding": emb_str}
            )
            rows2 = result2.fetchall()
            f.write(f"Results: {len(rows2)}\n")
            for row in rows2:
                similarity = 1 - row.distance
                f.write(f"  ID {row.id}: similarity={similarity:.4f}\n")
                f.write(f"    preview: {row.preview}...\n")
            
            f.write("\nTEST COMPLETE\n")
            
        finally:
            await db_gen.aclose()
    
    print(f"Output written to: {output_file}")

if __name__ == "__main__":
    asyncio.run(test_vector_search())
