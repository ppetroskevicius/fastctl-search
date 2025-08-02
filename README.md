# Real Estate Property Semantic Search Demo

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
