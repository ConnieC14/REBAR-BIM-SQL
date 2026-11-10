# FASTAPI
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from vector_db_agent_pipeline import get_agent_result


app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check
@app.get("/")
def health_check():
    """
    Quick health check endpoint for the application backend.

    Returns:
    ----------
        JSONResponse:
            A JSON response with a message confirming the backend is running.
    """
    return JSONResponse(content={"message": "Hello from the FastAPI backend!"})


# POST request handler
@app.post("/query")
async def handle_query(request: Request):
    """
    Handles a POST request from the Frontend.
    Retrieves a JSON object from the Frontend handleSubmit() method containing
    the 'name' key and the user's query and validates it.

    Parameters:
    ----------
    request : Request
        The incoming HTTP request object, containing the JSON data from the
        frontend.

    Returns:
    ----------
    JSONResponse:
        A JSON response containing the processed result from the `main`
        function.
    """
    try:
        data = await request.json()
        print("Received data: ", data)

        if not data:
            raise HTTPException(
                status_code=400, detail="No 'data' data received."
            )

        # Retrieves the User's Question.
        nameID = list(data.keys())[0]
        value = data.get(nameID)
        if not value:
            raise HTTPException(
                status_code=400, detail="No 'value' data received."
            )
        print(f'obtaining results: {value}')
        # Generate Response
        result = get_agent_result(value)
        print('Extracted results')
        # Sends the Frontend the response.
        return JSONResponse(content={"result": result})

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid 'data' data, Error: {e}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
