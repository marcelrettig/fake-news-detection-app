from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.endpoints import router as api_router

app = FastAPI(
    title="Fake News Detection API",
    description="Backend for Fake News Detection integrating LLM logic and real news article functions.",
    version="1.0.0"
)

# Enable CORS so that your React frontend can communicate during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify your frontend's domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the endpoints from endpoints.py.
app.include_router(api_router)

# Optional: A root endpoint to verify that the API is running.
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Fake News Detection API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

#Example Tweet Input
#tweet_text = ("EILMELDUNG – Europa wird 843 MILLIARDEN Dollar für Verteidigung ausgeben, darunter 158 MILLIARDEN Dollar an neuer Hilfe für die Ukraine."
#              "Dies kommt zusätzlich zu den Ausgaben einzelner Länder zur Unterstützung der Ukraine."
#              "Trumps und Putins Plan, die Ukraine zu zerstören, SCHEITERT.")

#tweet_text = ("Donald Trump und Elon Musk haben mit DOGE bisher die Verschwendung von mehr als 400 Milliarden Dollar verhindert! "
#            "Wer denkt dass das schlecht ist ist lost #Trump #Musk #DOGE")