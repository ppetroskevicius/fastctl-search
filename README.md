# Real Estate Property Semantic Search Demo

## Prompt1

I would like to create a semantic search demo for the real estate agency. I have real estate property data saved in the JSON format. I also created a data schema. Could you please suggest what kind of semantic searches on real estate properties I should be able to do on such data?

## Prompt2
Here are my demo system preferences: 

1. Local setup for the demo is fine.
2. The CLI interface is fine. No need to build API or web interface.
3. Use QdrantDB in a docker container or so.
4. I want to use Pydantic
5. I want to use OpenAI models for LLM. I have OPENAI_API_KEY setup in my environment. 
6. I want to build a hybrid search (semantic and structured). I want to use LLM to extract query elements for the structured query. I do not want to use legacy hard coded regex for extracting search keywords from the query. I has to be semantic natural language search. That is the purpose of the demo.
7. Preferably demo has to work with 3000 real estate properties.

Let's try with the CLI, test the search quality and then we will increase the complexity gradually.

## Project Structure

real_estate_search/
├── data/json/rent_details_20250519.json  # Input data
├── models.py                             # Pydantic models
├── index_properties.py                   # Indexing script
├── search_cli.py                         # CLI search script
├── .env                                  # OPENAI_API_KEY
└── qdrant_data/                          # QdrantDB storage (created by Docker)


## Setup

```bash
rm -Rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

```bash
pip install pydantic qdrant-client openai python-dotenv
docker ps
docker stop exciting_wright
docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:latest
python index_properties.py
python search_cli.py "Pet-friendly apartments in Minato-ku under ¥300,000/month"
python search_cli.py "Apartments near Omotesando Station within 10 minutes walk"
python search_cli.py "Apartments near Omotesando metro within 10 minutes walk"
python search_cli.py "New pet-friendly apartments under ¥250,000"
python search_cli.py "I have a cat. I am looking for the new apartments under ¥250,000"
python search_cli.py "I have a cat. I am looking for the new apartments for less than ¥200,000"
```
