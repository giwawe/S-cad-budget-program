from pydantic import BaseModel


class ProjectInput(BaseModel):
    project_name: str = "Untitled"
