#!/bin/bash
# Script to run styling demo via API

echo "Make sure your FastAPI server is running on port 8000"
echo "Make sure Ollama is running on port 11434"
echo ""
echo "Sending request to /summary_style endpoint..."
echo ""

curl -X POST http://localhost:8000/summary_style \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [
      {
        "id": "test_001",
        "title": "Tech Company Reports Strong Q3 Earnings",
        "body": "TechCorp announced Q3 revenue of $2.5 billion, up 15% year-over-year. The company credits growth to cloud services and AI products. CEO Jane Smith said the results reflect strong demand and operational efficiency. The company raised its full-year forecast and plans to expand into European markets next quarter.",
        "language": "en"
      }
    ],
    "writing_style": "journalistic",
    "output_format": "paragraph",
    "institutional": false,
    "additional_combinations": [
      {"writing_style": "academic", "output_format": "paragraph"},
      {"writing_style": "executive", "output_format": "paragraph"}
    ]
  }' | python3 -m json.tool

echo ""
echo "Done!"
