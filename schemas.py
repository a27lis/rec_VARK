from pydantic import BaseModel
from typing import List, Optional



class UserProfileSchema(BaseModel):
    age: int
    learning_styles: List[str]

    class Config:
        orm_mode = True


class RecommendationResponse(BaseModel):
    resource_id: int
    title: str
    link: str
    description: str
    learning_styles: str
    age_group: str
    relevance_score: float

    class Config:
        orm_mode = True