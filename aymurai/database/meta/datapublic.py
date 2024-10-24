from sqlmodel import Field, SQLModel


class Datapublic(SQLModel, table=True):
    id: int = Field(primary_key=True, autoincrement=True)
