import os
import pandas as pd
import chromadb
from dotenv import load_dotenv
from chromadb.utils import embedding_functions

# Load environment variables
load_dotenv()


def get_embedding_function():
    """
    EMBEDDING_PROVIDER=local (default) runs all-MiniLM-L6-v2 locally;
    EMBEDDING_PROVIDER=openai uses the OpenAI embeddings API.
    """
    if os.getenv("EMBEDDING_PROVIDER", "local").lower() == "openai":
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-ada-002"
        )
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


class ChromaDBManager:
    def __init__(self, db_path=None):
        # Keep one vector store per database so collections don't mix
        self.db_path = db_path or os.getenv("CHROMA_DB_PATH", "./chroma_db")
        os.makedirs(self.db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.openai_ef = get_embedding_function()

    def get_or_create_collection(self, collection_name):
        return self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.openai_ef,
            metadata={"description": "Database Schema information"}
        )

    def load_table_metadata(self, file_path):
        df = pd.read_csv(file_path)
        df = df[['Table Name', 'Chakri Notes']]
        return df

    def load_column_metadata(self, file_path):
        # Dictionary to store dataframes for each sheet
        sheet_data = {}
        excel_file = pd.ExcelFile(file_path)

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            df.columns = ['Column_Name', 'Column_Description']
            sheet_data[sheet_name] = df

        return sheet_data

    def insert_table_metadata(self, df, collection_name="table_metadata"):
        collection = self.get_or_create_collection(collection_name)

        if collection.count() == 0:
            documents = df['Table Name'].tolist()
            metadatas = [{'table_name': name} for name in df['Table Name'].tolist()]
            ids = [f"table_{name}" for name in df['Table Name'].tolist()]

            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} tables to {collection_name}")
        else:
            print(f"Collection {collection_name} already exists with {collection.count()} entries")
        
        return collection

    def insert_column_metadata(self, sheet_data, collection_name="column_metadata"):
        collection = self.get_or_create_collection(collection_name)
        
        if collection.count() == 0:
            documents = []
            metadatas = []
            ids = []
            
            for table_name, df in sheet_data.items():
                for _, row in df.iterrows():
                    documents.append(row['Column_Description'])
                    metadatas.append({
                        'table_name': table_name,
                        'column_name': row['Column_Name']
                    })
                    ids.append(f"col_{table_name}_{row['Column_Name']}")
            
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} columns to {collection_name}")
        else:
            print(f"Collection {collection_name} already exists with {collection.count()} entries")

        return collection

    def query_collection(self, collection_name, query, top_n=5):
        collection = self.chroma_client.get_collection(
            name=collection_name,
            embedding_function=self.openai_ef
        )
        return collection.query(
            query_texts=[query],
            n_results=top_n
        )


def main():
    try:
        # Initialize ChromaDB manager
        db_manager = ChromaDBManager()

        # Load and insert table metadata
        table_file_path = "./data/SQL_DATABASE_ANNOTATIONS_WITH_DESCRIPTIONS.csv"
        table_df = db_manager.load_table_metadata(table_file_path)
        table_collection = db_manager.insert_table_metadata(table_df)

        # Load and insert column metadata
        column_file_path = "./data/FINAL_column_names_with_descriptions.csv"  # Update with your second Excel file path
        sheet_data = db_manager.load_column_metadata(column_file_path)
        column_collection = db_manager.insert_column_metadata(sheet_data)
  
        while True:
            print("\nWhich metadata would you like to search?")
            print("1. Table metadata")
            print("2. Column metadata")
            print("3. Quit")
            
            choice = input("Enter your choice (1-3): ")
            
            if choice == "3":
                break
                
            collection_name = "table_metadata" if choice == "1" else "column_metadata"
            user_query = input("\nEnter your search query: ")
            
            results = db_manager.query_collection(collection_name, user_query)
            
            print("\nSearch Results:")
            print("-" * 50)
            
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                print(f"\nTable: {metadata['table_name']}")
                if 'column_name' in metadata:
                    print(f"Column: {metadata['column_name']}")
                print(f"Description: {doc}")
                print("-" * 50)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()