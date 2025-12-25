
from fastapi import FastAPI
from urls import root_router

app = FastAPI()

# Connect the central routing system
app.include_router(root_router)