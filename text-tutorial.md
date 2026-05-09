## Intro

Hi, recently I've been learning new thnigs about distributed systems
I noticed that there are a lot of theoretical videos about different patterns 
but no one really shows how to implement those concepts in practice.

That is why I decided to record this series about microservices.
I will use python and the most popular technologies like docker, k8s,
postgresql, kafka, redis, etc. You can take my code as a template
for your own project or just look at my implementation.

In this video we will implement project with two microservices 
and one poetry package for the shared code.
One microservice will manage users and other one will manage books. Next chapters
will be based on this project. We will implement CRUD endpoints,
unit tests, logging and database migrations. Also I will show
you how to implement docker compose environment for the development
and how to write kubernetes manifests to deploy the project. For database
we will use postgres because I feel like it is the most popular and
it is very convenient.

Full project code: [repo](https://github.com/Misha4231/distributed-systems-practical-couse/tree/main).

## What is a microservice?

Let's discuss what is a microservice and what its pros and cons are. 
If you are not interested in the theoretical part, feel free to jump
right into the implementation part.

First of all there are monoliths and microservices. A monolith is when
you have the entire project in one code base and you run it all together.
A microservice is a small, independent application that performs one
specific business function and communicates with other applications over a network.

For example, an e-commerce platform might have separate microservices for:
- user accounts
- product catalog
- payments
- inventory
- shipping
- notifications

Each service can be developed, deployed, scaled, and updated independently.

So insted of making internal calls and running the entire backend in one place we
are splitting it across machines and call different parts via the network.
That way each microservice has its own single responsibility and data storage.

## Pros and Cons

Microservices have many pros and cons, but I will point out the
ones that I find the most important.

### Pros:
1. Easier scaling

You can scale only the parts under heavy load. Every microservice
can run on a separate machine so you can add RAM or upgrade CPU
only where it is really needed.

Example:
- payment service gets little traffic
- search service gets massive traffic

You scale search independently instead of scaling the entire application.


2. Faster development

Different teams can work on different services simultaneously.

Example:
- Team A handles authentication
- Team B handles recommendations

3. Better fault isolation

If one service fails, the entire system may still partially work.

Example:
- recommendation engine crashes
- checkout still functions

In a monolith, one crash can sometimes affect everything.

### Cons:

1. Much higher operational complexity

This is the biggest downside.

You now manage:
- many deployments
- networking
- service discovery
- monitoring
- logging
- API gateways
- distributed tracing
- etc.

A simple monolith can be dramatically easier to operate.
You will see this throughout that series. Sometimes, things that
would take 100 lines of code in monolith will take 1000 in microservices.

2. Network latency and failures

Services communicate over networks, which introduces:
- delays
- retries
- timeouts
- partial failures

Function calls inside a monolith are much simpler and faster.
Network cable can be just physically break and that will be it
for our distributed system.

3. Data consistency challenges

We will discuss it and solve those challenges in the next chapters.
Basically in microservices each service may own its own database and
distributed transactions are difficult.

4. Harder local development and testing

You will see this today. When you are developing a single fastapi app
you can just run it with one command in terminal.
Running 20 services locally can be painful. We will use docker compose for that.


## Users microservice imlementation

I want to mention that I am expecting from you some basic knowledge of
how backend services are working and what is docker and databases. I'll try to
explain more complicated things.

Let's start with the users microservice. We will use
poetry as a package manager. Poetry is something similar to pip
but better because it solves dependency version issues for us.

```bash
poetry new user-service
```
That command will create python project with pyproject.toml, source folder
and tests folder.

Let's install needed libraries:
```bash
poetry add fastapi sqlalchemy pydantic pydantic-settings alembic psycopg2-binary asyncpg structlog
```

Let's define kind of basic folders structure for
our microservices. FastAPI does not provide us with template
so I will stick to the standards.

```
.
├── poetry.lock
├── pyproject.toml
├── README.md
├── tests
│   └── __init__.py
└── user_service
    ├── core
    │   └── __init__.py
    ├── __init__.py
    ├── main.py
    ├── models
    │   └── __init__.py
    ├── routes
    │   └── __init__.py
    ├── schemas
    │   └── __init__.py
    ├── middlewares
    │  └── __init__.py
    └── services
        └── __init__.py
```

in main.py we will just create an app object, add middlewares and routes.
```python
from fastapi import FastAPI

from user_service.routes import users

app = FastAPI()
app.include_router(users.router)
```

let's also create the route for CRUD endpoints
routes/users.py:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def get_users():
    return {"status": "ok"}
```

Here you have endpoint that just return status json.
I like to start with the environment setup so that we
can easiy run code and test it. That is why I will
leave that endpoint for now and we will get back to it later.

Let's add connection to the database. We will asyncronous sqlalchemy
with postgres. Database session will be created with dependency injection.

core/database.py:
```python
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

from user_service.core.settings import settings

DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_db,
)
engine = create_async_engine(DATABASE_URL, isolation_level="REPEATABLE READ")

AsyncSessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    bind=engine,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

We are using asyncpg because I want to make connection asyncronous. Sometimes it will
make the code more complex, but also will make it faster.

I decided to use REPEATABLE READ isolation level because it will cover our needs in that tutorial.
There are more levels in databases, you can read about them more detaily in other articles.
REPEATABLE READ will ensure that data won't change when we are reading it in transaction.

In sessionmaker I am disabling autoflush, autocommit and expire_on_commit because sometimes it will come handy
to make it manually. Disabled expire_on_commit will make sure that after commit we will still be able to use data
that we got earlier.

get_db is the dependency injection that will give us database session.

Also as you see, we got to load the settings from environment variables to have database credentials.
To load that data we will create
core/settings.py:
```python
from pydantic_settings import BaseSettings


# Reads from environment variables
class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: str
    postgres_db: str


settings = Settings()
```

pydantic will match environment variables with settings class fields.

Now let's write model for the table that will hold user data.
models/base.py
```python
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

Model = declarative_base()


class TimeStampedModel(Model):
    __abstract__ = True

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Here we are creating Model that is inherited in each model and TimeStampedModel that we will inherit
in models where we want to store the creating and updating timestamps for each row.

models/user.py
```python
from sqlalchemy import Column, Integer, DECIMAL, String

from user_service.models.base import TimeStampedModel


class User(TimeStampedModel):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(100), nullable=False)
    balance = Column(DECIMAL(8, 2), default=0)
```

User model is inherits TimeStampedModel so it will have columns: id, name, balance, create_at and updated_at.


Also let's define schemas for out api. The difference between 
model and schema is that model represents full table in database
but schema represents fields from json that api will take, return or use just internally.

schemas/user.py
```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    name: str
    balance: float


class UserUpdate(BaseModel):
    name: str | None = None
    balance: int | None = None


class UserOut(BaseModel):
    id: int
    name: str
    balance: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- UserCreate is the data taht api needs to receive to create a new user row in database.
- UserUpdate is the data taht api needs to receive to update a user in database.
- UserOut is the data that api will return when user object is requested (from_attributes
  is a configuration that allows us map fields from model to schema)

now we can write service for actions with user
(sometimes that service can be called controller but I prefer that name).
Basically it is just a new layer that does not know about http requests.
Routes or other parts will call service functions. 

Let's start with getting all the users in a list
services/users.py:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from user_service.models.user import User

async def get_all_users(db: AsyncSession):
    result = await db.execute(select(User))
    users = result.scalars().all()

    return users
```

service function receives database session and just select all user rows.
!!In real project it is better to implement pagination and caching!!
but that is not the point of the tutorial so I don't want to spend your time on it.

routes/users.py:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from user_service.core.database import get_db
from user_service.schemas.user import UserOut
from user_service.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserOut])
async def get_users(db: AsyncSession = Depends(get_db)):
    try:
        users = await user_service.get_all_users(db)

        return users
    except Exception as e:
        raise
```

here we are just calling the service function and return the result.
If some error occur (for example database server crushed) we will return a 500 internal error.


Now, before writing more endpoints, I want to try to run what we already have.
We will use docker compose for the development environment because we will
have a lot of services and multiple database instances. Nobody want's to
open 10 terminal and spin up postgres on a different ports.

Let's start by writing Dockerfile. It is basically a docker image for the user microservice.
user-service/Dockerfile:
```Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

# install pg client for pg_ready
RUN apt-get update && apt-get install -y postgresql-client

RUN pip install --upgrade pip
RUN pip install poetry

COPY user-service/pyproject.toml user-service/poetry.lock* /app/user-service/

WORKDIR /app/user-service
RUN poetry config virtualenvs.create false && poetry install --no-root

FROM builder

WORKDIR /app

ENV PYTHONPATH=/app

COPY wait-for-db.sh /app/wait-for-db.sh
COPY user-service/ /app/user-service

EXPOSE 8000
```

Here we have 2 stages of building an image:
1. install postgres client, copy pyproject.toml and insall dependencies 
2. inherit builder with everything needed, copy wait-for-db.sh bash script and expose port

We will spin up the application outside the Dockerfile to make it more reusable.
For example in unit tests we need to build the image but we don't want to start http server.

We are using path on one directory higher than docker file because we will have one global docker compose.

/wait-for-db.sh:
```bash
#!/bin/sh

while true; do
  pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT

  if [ $? -eq 0 ]; then
    echo "DB is ready!"
    break
  fi

  echo "no response"
  sleep 1
done
```

in dockerfile we installed the postgresql-client to use pg_isready. This is the command that will
check if postgres if fully ready to accept connections.

Now, let's write docker compose with postgres and api
/docker-compose.yml:
```yaml
services:
  users_service_db:
    image: postgres
    env_file:
      user-service/.env
    ports:
      - "5434:5432"
    volumes:
      - users_postgres_data:/var/lib/postgresql
    restart: always
    
  users_api:
    build: 
      dockerfile: user-service/Dockerfile
      context: .
    env_file:
      user-service/.env
    depends_on:
      - users_service_db
    ports:
      - "8000:8000"
    develop:
      watch:
        - path: ./user-service/user_service
          action: rebuild
          target: /app/user-service
        
    working_dir: /app/user-service
    volumes:
      - ./user-service:/app/user-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        uvicorn user_service.main:app --host 0.0.0.0 --port 8000
      "

volumes:
  users_postgres_data:
```

as you see here we are starting the poistgres instance and expose port 5434.
You can use another port that is free on your machine.

The interesting part in users_api container that I want you to look closer
is `develop:` part. docker compose will track all files in source folder of
the microservice and rebuild the app if we make some changes. It will
make development much easier because we won't have to rebuild everyting after each change.

Also we have `command:` part. Those commands are executed after docker image was built.
We are waiting for the database and start uvicorn server.

We need to create .env file to pass it into the docker compose.
In real projects you must put .env file to the .gitignore. Only for the purpose
of the tutorial I will leave it in the repo.

user-service/.env
```.env
# IN REAL PROJECTS .env MUUUUST BE IN .gitignore!!!

POSTGRES_USER=users
POSTGRES_PASSWORD=secret
POSTGRES_HOST=users_service_db
POSTGRES_PORT=5432
POSTGRES_DB=users
```

postgres needs only POSTGRES_DB, POSTGRES_PASSWORD and POSTGRES_USER but we are adding more 
for the fastapi app because I don't want to make 2 separate files.

let's try to run what we have (use `--watch` flag to track changes)
```bash
docker-compose -f docker-compose.yml up --build --watch
```

We will se the error saying that we don't have uvicorn installed.
```bash
cd user-service
poetry add uvicorn
```

I already have my postman setup to send requests and if we send one we will see
that `users` table does not exist in database.
The reason for it is that we didn't write any migrations.

go to the microservice directory and init alembic migrations
```bash
cd user-service
alembic init migrations
```

alembic is just a tool taht works close to the sqlalchemy orm.
It will track the state of database schema and we will programaticaly 
add new tables, columns, indecies, etc.

in `migrations` folder we have `env.py` for the environment configuration and 
`versions` folder to store out migration scripts.

all we need to do in `env.py` is change the url to the database
because we want to take it from our environment variables

migrations/env.py:
```python
import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy.engine import URL

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def env_database_url() -> URL:
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
    )

    return DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = env_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = env_database_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Now we can add new revision where we will create users table
```bash
alembic revision -m "create users table"
```

migrations/versions/2d036ff97351_create_users_table.py:
```python
"""create users table

Revision ID: 2d036ff97351
Revises: 
Create Date: 2026-05-07 13:01:23.699935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = '2d036ff97351'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("balance", sa.DECIMAL(8, 2), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("users")
```

we could have automate the process of running migrations in docker container
but I prefer to do it manually while we are developping. Later with
tests and in k8s we will automate it

run docker compose:
```bash
docker-compose -f docker-compose.yml up --build --watch
```

in seapate terminal run migraions:
```bash
docker-compose exec -it users_api alembic upgrade head
```

Now, try to send a request.
Endpoint should answer you with `200 Success` and empty array.

Great, we just made our first endpoint in microservice.


Now let's make it better. Every backend should have logs.
Logs are like messages after crutial steps in code reading witch we
can decide if everything was right or some issue occured.

We will write logs with `structlog` library but logging libraries are pretty similar
so it is up to you what you will use. I like `structlog` because it provides
easy way to implement what we need for that tutorial.

Every request will be assigned to the request id. We will generate
unique id for each request so that later we can filter and track full trace.
If you never worked with logs, it could make no sense for you, but
trust me, it is very useful when you try to find what happened to some user.

core/context.py:
```python
from contextvars import ContextVar

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
```

we need context variable to store request_id globaly through the request

core/logging.py:
```python
import structlog

from user_service.core.context import request_id_ctx_var


def add_request_id(_, __, event_dict):
    event_dict["request_id"] = request_id_ctx_var.get()
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        add_request_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


logger: structlog.PrintLogger = get_logger()
```

processors in structlog if just a set of functions that will be called in
order to fully create the request. For the each log, we are adding timestamp,
log level and our request id that we are gettig from global context.

Also, we need to add middleware that will generate the request id and assign it
to the context.

middlewares/logging.py:
```python
import uuid

from fastapi import Request

from user_service.core.context import request_id_ctx_var


async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())

    request_id_ctx_var.set(request_id)
    request.state.request_id = request_id

    response = await call_next(request)

    return response
```

we also have to add that middleware to the fastapi app object.
main.py:
```python
from fastapi import FastAPI

from user_service.routes import users
from user_service.middlewares.logging import logging_middleware

app = FastAPI()
app.middleware("http")(logging_middleware)
app.include_router(users.router)
```

Let's add logs for our endpoint
routes/users.py:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from user_service.core.database import get_db
from user_service.schemas.user import UserOut
from user_service.services import users as user_service
from user_service.core.logging import logger

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserOut])
async def get_users(db: AsyncSession = Depends(get_db)):
    logger.info("get_users_start")

    try:
        users = await user_service.get_all_users(db)

        logger.info("get_users_success", users_count=len(users))
        return users

    except Exception as e:
        logger.error("get_users_failed", error=str(e))
        raise
```

services/users.py:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from user_service.models.user import User
from user_service.core.logging import logger

async def get_all_users(db: AsyncSession):
    logger.debug("service_get_all_users_start")

    result = await db.execute(select(User))
    users = result.scalars().all()

    logger.debug("service_get_all_users_success", users_count=len(users))

    return users
```

in terminal you will see logs similar to those:
```
users_api-1         | {"event": "get_users_start", "level": "info", "request_id": "eb9abcd4-884a-4961-8171-975fdd5a1159", "timestamp": "2026-05-07T11:45:57.162018Z"}
users_api-1         | {"event": "service_get_all_users_start", "level": "debug", "request_id": "eb9abcd4-884a-4961-8171-975fdd5a1159", "timestamp": "2026-05-07T11:45:57.162089Z"}
users_api-1         | {"users_count": 0, "event": "service_get_all_users_success", "level": "debug", "request_id": "eb9abcd4-884a-4961-8171-975fdd5a1159", "timestamp": "2026-05-07T11:45:57.197741Z"}
users_api-1         | {"users_count": 0, "event": "get_users_success", "level": "info", "request_id": "eb9abcd4-884a-4961-8171-975fdd5a1159", "timestamp": "2026-05-07T11:45:57.198011Z"}
```

Great, now as we have database and logging configured, we can
imeplement the rest of the endpoints.


routes/users.py:
```python
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from user_service.core.database import get_db
from user_service.schemas.user import UserCreate, UserOut, UserUpdate
from user_service.services import users as user_service
from user_service.core.logging import logger

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserOut])
async def get_users(db: AsyncSession = Depends(get_db)):
    logger.info("get_users_start")

    try:
        users = await user_service.get_all_users(db)

        logger.info("get_users_success", users_count=len(users))
        return users

    except Exception as e:
        logger.error("get_users_failed", error=str(e))
        raise


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("get_user_start", user_id=user_id)

    try:
        user = await user_service.get_user(user_id, db)

        logger.info("get_user_success", user_id=user_id)
        return user
    except NoResultFound:
        logger.warning("get_user_not_found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error("get_user_error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500)


@router.post("/", response_model=UserOut)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    logger.info("create_user_start", name=data.name, balance=data.balance)

    try:
        user = await user_service.create_user(data, db)

        logger.info("create_user_success", user_id=user.id)
        return JSONResponse(content=jsonable_encoder(user), status_code=201)

    except Exception as e:
        logger.error("create_user_failed", error=str(e))
        raise


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_db)
):
    logger.info(
        "update_user_start", user_id=user_id, name=data.name, balance=data.balance
    )

    try:
        user = await user_service.update_user(user_id, data, db)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info("update_user_success", user_id=user_id)
        return user

    except HTTPException:
        logger.warning("update_user_not_found", user_id=user_id)
        raise

    except Exception as e:
        logger.error("update_user_failed", user_id=user_id, error=str(e))
        raise


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(
        "delete_user_start",
        user_id=user_id,
    )

    try:
        await user_service.delete_user(user_id, db)

        logger.info("delete_user_success", user_id=user_id)

        return Response(status_code=204)
    except NoResultFound:
        logger.warning("delete_user_not_found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error("delete_user_error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500)
```

services/users.py:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.exc import NoResultFound

from user_service.models.user import User
from user_service.schemas.user import UserCreate, UserUpdate
from user_service.core.logging import logger


async def get_all_users(db: AsyncSession):
    logger.debug("service_get_all_users_start")

    result = await db.execute(select(User))
    users = result.scalars().all()

    logger.debug("service_get_all_users_success", users_count=len(users))

    return users


async def get_user(user_id: int, db: AsyncSession):
    logger.debug("service_get_user_start", user_id=user_id)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("service_get_user_not_found", user_id=user_id)
        raise NoResultFound()

    logger.debug("service_get_user_success", user_id=user_id)

    return user


async def create_user(data: UserCreate, db: AsyncSession):
    logger.debug("service_create_user_start", name=data.name, balance=data.balance)

    try:
        user = User(**data.model_dump())
        db.add(user)

        await db.commit()
        await db.refresh(user)

        logger.debug("service_create_user_success", user_id=user.id)

        return user

    except Exception as e:
        logger.error("service_create_user_failed", error=str(e))
        raise


async def update_user(user_id: int, data: UserUpdate, db: AsyncSession):
    logger.info(
        "service_update_user_start",
        user_id=user_id,
        name=data.name,
        balance=data.balance,
    )

    try:
        values = {}

        if data.name is not None:
            values["name"] = data.name
        if data.balance is not None:
            values["balance"] = data.balance

        if not values:
            logger.info("service_update_user_no_fields", user_id=user_id)
            return None

        result = await db.execute(
            update(User).where(User.id == user_id).values(**values).returning(User)
        )

        user = result.scalar_one_or_none()
        await db.commit()

        if not user:
            logger.warning("service_update_user_not_found", user_id=user_id)
            return None

        logger.info("service_update_user_success", user_id=user_id)

        return user

    except Exception as e:
        logger.error("service_update_user_failed", user_id=user_id, error=str(e))
        raise


async def delete_user(user_id: int, db: AsyncSession):
    logger.info(
        "service_delete_user_start",
        user_id=user_id,
    )

    try:
        result = await db.execute(
            delete(User).where(User.id == user_id).returning(User.id)
        )
        deleted_id = result.scalar_one_or_none()
        await db.commit()

        if deleted_id is None:
            logger.warning(
                "service_delete_user_not_found",
                user_id=user_id,
            )
            raise NoResultFound()

        logger.info("service_delete_user_success", user_id=user_id)

        return True

    except Exception as e:
        logger.error("service_delete_user_failed", user_id=user_id, error=str(e))
        raise
```


The only thing that is left here are unit tests.
Poetry already created tests folder for us. We will imeplement tests there.

let's install dependencies needed for unit tests
```bash
poetry add pytest anyio mock httpx psycopg
```

create `conftest.py` file in tests. Pytest will use that file
as a configuration file. We will define fixtures there.

tests/conftest.py:
```python
import os

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from httpx import AsyncClient, ASGITransport
from sqlalchemy import NullPool
from sqlalchemy.engine import URL

from user_service.models.base import Model
from user_service.main import app
from user_service.core.database import get_db


pytest_plugins = ["anyio"]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# Setup test database engine
@pytest.fixture(scope="session")
def test_engine():
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
    )
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    return engine


# Setup test database
@pytest.fixture(scope="session")
async def setup_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)

    await test_engine.dispose()


# Setup test database session
@pytest.fixture
async def db_session(test_engine: AsyncEngine, setup_db):
    conn = await test_engine.connect()
    transaction = await conn.begin()

    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",  # data is not really saved in database so that tests are isolated
    )

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
            await conn.close()

# Setup http client
@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://users_test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

Let's go one by one. We are using `anyio` plugin because 
our fastapi app runs asyncronusly so we have to make our tests also async.
AnyIO abstracts libraries like `asyncio` or `trio` so they can support
multiple async backends with one codebase.

fixtures:
- `anyio_backend` - tells anyio witch backend should it use for all tests.
- `test_engine` - creates database url from an environment variables and creates engine.
  we use `poolclass=NullPool` so that connection is closed right after running tests.
- `setup_db` - takes database engine, opens connection and create all tables. Than at the end
  it drops all tables and dispose the engine. You can this of taht fixture as of migrations
- `db_session` - this fixture is the most important one because here we are opening the session
  we will use created session from that fixture in tests to modify database.
  Notice that we are using `create_savepoint` as a transaction mode. It will
  ensure all the data is not really stored in database at each test and every
  test will have empty database.
- `client` - creates the async http client for the tests where we will send request to individual routes.
  Also notice that here we are overriding out get_db depencency injection. One of the biggest advantages of DI
  is that we can override it on testing and use the needed session.

Now as we have fixtures setted up, we can write unit tests.
tests/test_services/test_user_service.py:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound
from sqlalchemy import select

from user_service.services import users as user_service
from user_service.schemas.user import UserCreate, UserUpdate
from user_service.models.user import User


@pytest.mark.anyio
async def test_create_user(db_session: AsyncSession):
    data = UserCreate(name="test", balance=100)

    user = await user_service.create_user(data, db_session)

    assert user.id is not None
    assert user.name == "test"
    assert user.balance == 100


@pytest.mark.anyio
async def test_create_user_persisted(db_session: AsyncSession):
    data = UserCreate(name="persist", balance=50)

    user = await user_service.create_user(data, db_session)

    result = await db_session.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one()

    assert db_user.name == "persist"
    assert db_user.balance == 50


@pytest.mark.anyio
async def test_get_all_users_empty(db_session: AsyncSession):
    users = await user_service.get_all_users(db_session)
    assert users == []


@pytest.mark.anyio
async def test_get_all_users_multiple(db_session: AsyncSession):
    await user_service.create_user(UserCreate(name="a", balance=1), db_session)
    await user_service.create_user(UserCreate(name="b", balance=2), db_session)

    users = await user_service.get_all_users(db_session)

    assert len(users) == 2


@pytest.mark.anyio
async def test_get_user_success(db_session: AsyncSession):
    user = await user_service.create_user(UserCreate(name="a", balance=10), db_session)

    fetched = await user_service.get_user(user.id, db_session)

    assert fetched.id == user.id
    assert fetched.name == "a"


@pytest.mark.anyio
async def test_get_user_not_found(db_session: AsyncSession):
    with pytest.raises(NoResultFound):
        await user_service.get_user(999, db_session)


@pytest.mark.anyio
async def test_update_user_full(db_session: AsyncSession):
    user = await user_service.create_user(UserCreate(name="a", balance=10), db_session)

    updated = await user_service.update_user(
        user.id, UserUpdate(name="updated", balance=50), db_session
    )

    assert updated.name == "updated"
    assert updated.balance == 50


@pytest.mark.anyio
async def test_update_user_partial_name(db_session: AsyncSession):
    user = await user_service.create_user(UserCreate(name="a", balance=10), db_session)

    updated = await user_service.update_user(
        user.id, UserUpdate(name="new"), db_session
    )

    assert updated.name == "new"
    assert updated.balance == 10


@pytest.mark.anyio
async def test_update_user_partial_balance(db_session: AsyncSession):
    user = await user_service.create_user(UserCreate(name="a", balance=10), db_session)

    updated = await user_service.update_user(
        user.id, UserUpdate(balance=999), db_session
    )

    assert updated.name == "a"
    assert updated.balance == 999


@pytest.mark.anyio
async def test_update_user_not_found(db_session: AsyncSession):
    result = await user_service.update_user(999, UserUpdate(name="x"), db_session)

    assert result is None


@pytest.mark.anyio
async def test_update_user_no_fields(db_session: AsyncSession):
    user = await user_service.create_user(UserCreate(name="a", balance=10), db_session)

    result = await user_service.update_user(
        user.id,
        UserUpdate(),  # empty payload
        db_session,
    )

    assert result is None


@pytest.mark.anyio
async def test_delete_user_success(db_session: AsyncSession):
    user = await user_service.create_user(UserCreate(name="a", balance=10), db_session)

    result = await user_service.delete_user(user.id, db_session)

    assert result is True

    # verify deletion
    res = await db_session.execute(select(User).where(User.id == user.id))
    assert res.scalar_one_or_none() is None


@pytest.mark.anyio
async def test_delete_user_not_found(db_session: AsyncSession):
    with pytest.raises(NoResultFound):
        await user_service.delete_user(999, db_session)
```

In the service tests we are only calling service functions and passing
our `db_session` that we got from the fixture. Also to make tests async we use `@pytest.mark.anyio`


tests/test_routes/test_user_routes.py:
```python
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_route_create_user(client: AsyncClient):
    new_user_data = {"name": "test", "balance": 100}

    response = await client.post("/users/", json=new_user_data)
    data = response.json()

    assert response.status_code == 201
    assert data["name"] == new_user_data["name"]
    assert data["balance"] == new_user_data["balance"]
    assert "id" in data


@pytest.mark.anyio
async def test_route_list_all_users(client: AsyncClient):
    new_user_data = {"name": "test1", "balance": 101}

    await client.post("/users/", json=new_user_data)
    response = await client.get("/users/")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["name"] == new_user_data["name"]
    assert data[0]["balance"] == new_user_data["balance"]
    assert "id" in data[0]
    assert "created_at" in data[0]
    assert "updated_at" in data[0]


@pytest.mark.anyio
async def test_route_get_user_by_id(client: AsyncClient):
    new_user_data = {"name": "test2", "balance": 141}

    create_response = await client.post("/users/", json=new_user_data)
    new_user = create_response.json()

    response = await client.get(f"/users/{new_user['id']}")
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == new_user_data["name"]
    assert data["balance"] == new_user_data["balance"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.anyio
async def test_route_get_user_by_id_not_found(client: AsyncClient):
    response = await client.get(f"/users/999")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_user(client: AsyncClient):
    new_user_data = {"name": "test2", "balance": 141}

    create_response = await client.post("/users/", json=new_user_data)
    new_user = create_response.json()

    response = await client.put(
        f"/users/{new_user['id']}", json={"name": "updated", "balance": 20}
    )
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "updated"
    assert data["balance"] == 20


@pytest.mark.anyio
async def test_update_user_not_found(client: AsyncClient):
    response = await client.put("/users/999", json={"name": "x"})

    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_user(client: AsyncClient):
    new_user_data = {"name": "test2", "balance": 141}

    create_response = await client.post("/users/", json=new_user_data)
    new_user = create_response.json()

    response = await client.delete(f"/users/{new_user['id']}")

    assert response.status_code == 204

    # ensure it's gone
    response = await client.get(f"/users/{new_user['id']}")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_user_not_found(client: AsyncClient):
    response = await client.delete("/users/999")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_user_invalid_payload(client: AsyncClient):
    response = await client.post("/users/", json={"name": 123, "balance": "invalid"})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_update_partial(client: AsyncClient):
    new_user_data = {"name": "test2", "balance": 141}

    create_response = await client.post("/users/", json=new_user_data)
    new_user = create_response.json()

    response = await client.put(f"/users/{new_user['id']}", json={"name": "only_name"})

    data = response.json()

    assert data["name"] == "only_name"
    assert data["balance"] == 141
```

In route tests we are calling the http route rather than call individual functions.

We will run test with docker compose because like before it will make our
development easier in a long run.

/docker-compose-test.yml:
```yaml
services:
  users_test_db:
    image: postgres
    env_file:
      - user-service/.env.test
    ports:
      - "5433:5432"
    tmpfs: # auto clean
      - /var/lib/postgresql/data
    restart: always

  users_test:
    build: 
      dockerfile: user-service/Dockerfile
      context: .
    env_file:
      user-service/.env.test
    depends_on:
      - users_test_db
    working_dir: /app/user-service
    volumes:
      - ./user-service:/app/user-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        alembic upgrade head &&
        poetry run pytest -v
      "
```

This docker compose looks similar to the previous one but notice that we store
postges data in a temporary storage and we are running alembic migrations before 
starting the pytest.
Also I decided to make separate .env file for the tests because in real
world we sometimes need to run tests on a different server.

user-service/.env.test:
```env
POSTGRES_USER=test
POSTGRES_PASSWORD=test
POSTGRES_HOST=users_test_db
POSTGRES_PORT=5432
POSTGRES_DB=test
```

Now let's try to run our tests:
```bash
docker-compose -f docker-compose-test.yml run --rm users_test
```

we are using `run` with `--rm` flag to select single container we want to run.
Postgres is also spinning up because we have it in the `depends_on`.



Great. We have fully working users microservice.


## Books microservice imlementation

Books service essentially will be really similar to the users.
What I rather want to show you now is the problems that can occur
when you write microservices with similar configuration and how
to solve them.

Let's start with the same command for creating poetry project and installing dependencies
```bash
poetry new book-service
cd book-service/
poetry add fastapi ruff sqlalchemy pydantic pydantic-settings alembic psycopg2-binary asyncpg structlog uvicorn pytest anyio mock httpx psycopg
```

also let's make the same folder structure like in the user microservice
```
.
├── book_service
│   ├── core
│   │   └── __init__.py
│   ├── __init__.py
│   ├── main.py
│   ├── models
│   │   └── __init__.py
│   ├── routes
│   │   └── __init__.py
│   ├── schemas
│   │   └── __init__.py
│   └── services
│       └── __init__.py
├── poetry.lock
├── pyproject.toml
├── README.md
└── tests
    └── __init__.py
```

and now like before let's create the model, schemas and the firt route.

book_service/main.py:
```python
from fastapi import FastAPI

from book_service.routes import books

app = FastAPI()
app.include_router(books.router)
```

book_service/routes/books.py:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/")
async def get_books():
    return {"status": "ok"}
```

book_service/schemas/book.py:
```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookCreate(BaseModel):
    title: str
    author: str
    stock: int
    price: float


class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    stock: int | None = None
    price: float | None = None


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    stock: int
    price: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

book_service/models/base.py:
```python
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

Model = declarative_base()


class TimeStampedModel(Model):
    __abstract__ = True

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

book_service/models/book.py:
```python
from sqlalchemy import Column, Integer, String, DECIMAL

from book_service.models.base import TimeStampedModel


class Book(TimeStampedModel):
    __tablename__ = "books"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    author = Column(String(100), nullable=True)
    stock = Column(Integer, nullable=False, default=0)
    price = Column(DECIMAL(8, 2), nullable=False)
```

Now notice that we have some code repetition in each microservice. We haven't
configure database and logging but we already see it.
We have the same `TimeStampedModel` model that is inherited by both `Book` and `User` models.
In a development process you will notice that we have a lot of common stuff for each service.
If we just copy and paste, it could be a serious maintainance issue in future.
What if we would have ten microservices and suddelny we would have to make some
changes in logging configuration.

We already started to implement the book service, but let's jump back and do some refactoring.

## Shared library

For the shared code we will create a new poetry package and we will
load it as a dependency for every project.

go to the root and create this new project
```bash
poetry new common
cd common
poetry add pytest pydantic-settings pydantic fastapi sqlalchemy structlog
```

common package will contain middlewares, logging config, database config, shared schemas, fixtures and shared models.

create particular folder structure in common source:
```
.
├── common
│   ├── app.py
│   ├── core
│   │   └── __init__.py
│   ├── __init__.py
│   ├── middlewares
│   │   └── __init__.py
│   ├── models
│   │   └── __init__.py
│   └── tests
│       └── __init__.py
├── poetry.lock
├── pyproject.toml
└── README.md
```

Now we will move code from the user service
user_service/core/context.py -> common/core/context.py
user_service/core/database.py -> common/core/database.py
user_service/core/settings.py -> common/core/settings.py
user_service/core/logging.py -> common/core/logging.py

also fix the import names from `user_service` to `common`
see  the full code in [repo](https://github.com/Misha4231/distributed-systems-practical-couse/tree/main).

The only serious change is in the logging.py
common/core/logging.py:
```python
def get_logger() -> structlog.PrintLogger:
    logger: structlog.PrintLogger = structlog.get_logger()
    return logger
```

user_service/core/logging.py:
```python
import structlog

from common.core.logging import get_logger

logger: structlog.PrintLogger = get_logger()
```

also move the logging middleware and base from models to the common package
user_service/middleware/logging.py -> common/middleware/logging.py
user_service/models/base.py -> common/models/base.py

!Don't forget to fix imports from `user_service` and `book_service` to `common`!

common/app.py:
```python
from fastapi import FastAPI

from common.middlewares.logging import logging_middleware

def create_base_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(logging_middleware)
    return app
```

user_service/main.py:
```python
from fastapi import FastAPI

from user_service.routes import users
from common.app import create_base_app

app: FastAPI = create_base_app()
app.include_router(users.router)
```

common/tests/db_conf.py:
```pytnon
import os

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy import NullPool, text
from sqlalchemy.engine import URL

from common.models.base import Model

pytest_plugins = ["anyio"]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# Setup test database engine
@pytest.fixture(scope="session")
def test_engine():
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
    )
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    return engine


# Setup test database
@pytest.fixture(scope="session")
async def setup_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)

    await test_engine.dispose()


# Setup test database session
@pytest.fixture
async def db_session(test_engine: AsyncEngine, setup_db):
    conn = await test_engine.connect()
    transaction = await conn.begin()

    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",  # data is not really saved in database so that tests are isolated
    )

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
            await conn.close()
```

we will leave client fixture outside the common package because it
contains logic directly related to the app obect

user-service/tests/conftest.py:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import URL

from user_service.main import app
from common.core.database import get_db

pytest_plugins = ["common.tests.db_conf"]

# Setup http client
@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://users_test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

And finally we have to add common to the pyproject.toml to load that dependency
user-service/pyproject.toml:
```toml
[tool.poetry.dependencies]
...
common = "^0.1.0"

[tool.poetry.group.local.dependencies]
common = { path = "../common", develop = true }
```

we have all of the code in a single repository so we are loading it just from the top directory.
In real world, more popular approach is to create depencency on a remote storage (for example pip).

We set `develop=true` so that changes are pulled automatically and we don't have to change
the package version every time.

dockerfile and docker compose will also be slightly changed because we have to load
common package directory.

user-service/Dockerfile:
```Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

# install pg client for pg_ready
RUN apt-get update && apt-get install -y postgresql-client

RUN pip install --upgrade pip
RUN pip install poetry

COPY common /app/common
COPY user-service/pyproject.toml user-service/poetry.lock* /app/user-service/

WORKDIR /app/user-service
RUN poetry config virtualenvs.create false && poetry install --no-root

FROM builder

WORKDIR /app

ENV PYTHONPATH=/app

COPY wait-for-db.sh /app/wait-for-db.sh
COPY common/ /app/common
COPY user-service/ /app/user-service

EXPOSE 8000
```

docker-compose.yml:
```yaml
services:
  users_service_db:
    image: postgres
    env_file:
      user-service/.env
    ports:
      - "5434:5432"
    volumes:
      - users_postgres_data:/var/lib/postgresql
    restart: always
    
  users_api:
    build: 
      dockerfile: user-service/Dockerfile
      context: .
    env_file:
      user-service/.env
    depends_on:
      - users_service_db
    ports:
      - "8000:8000"
    develop:
      watch:
        - path: ./user-service/user_service
          action: rebuild
          target: /app/user-service
        - path: ./common/common
          action: rebuild
          target: /app/common
    working_dir: /app/user-service
    volumes:
      - ./common:/app/common
      - ./user-service:/app/user-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        uvicorn user_service.main:app --host 0.0.0.0 --port 8000
      "

volumes:
  users_postgres_data:
```

docker-compose-test.yml:
```yaml
services:
  users_test_db:
    image: postgres:15
    env_file:
      - user-service/.env.test
    ports:
      - "5433:5432"
    tmpfs: # auto clean
      - /var/lib/postgresql/data
    restart: always

  users_test:
    build: 
      dockerfile: user-service/Dockerfile
      context: .
    env_file:
      user-service/.env.test
    depends_on:
      - users_test_db
    working_dir: /app/user-service
    volumes:
      - ./common:/app/common
      - ./user-service:/app/user-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        alembic upgrade head &&
        poetry run pytest -v
      "
```

Before we run anything, we have to lock poetry and reset docker cache
```bash
cd user-service
poetry lock
cd ..
docker-compose -f docker-compose-test.yml build --no-cache
```

and now let's try to run tests to make sure everything is good
```bash
docker-compose -f docker-compose-test.yml run --rm users_test
```


## Back to the books microservice

Let's get back to the books microservice.
First of all we have to add `common` package.

book-service/pyproject.toml:
```toml
[tool.poetry.dependencies]
...
common = "^0.1.0"

[tool.poetry.group.local.dependencies]
common = { path = "../common", develop = true }
...
```

Also, delete `book_service/models/base.py` because we
have `Model` declaration inside `common` and edit the book model import:

book_service/models/book.py:
```python
from sqlalchemy import Column, Integer, String, DECIMAL

from common.models.base import TimeStampedModel


class Book(TimeStampedModel):
    __tablename__ = "books"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    author = Column(String(100), nullable=True)
    stock = Column(Integer, nullable=False, default=0)
    price = Column(DECIMAL(8, 2), nullable=False)
```

create fastapi app with the function from `common`
book_service/main.py:
```python
from fastapi import FastAPI

from book_service.routes import books
from common.app import create_base_app

app: FastAPI = create_base_app()
app.include_router(books.router)
```

and create the logger object

book_service/core/logging.py:
```python
import structlog

from common.core.logging import get_logger

logger: structlog.PrintLogger = get_logger()
```

Before implementing api endpoints, let's edit docker compose
so we can run it and check if everything is working

docker image will be the same as in user service the only
thing we are changing is a naming

book-service/Dockerfile:
```Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install poetry

COPY common /app/common
COPY book-service/pyproject.toml book-service/poetry.lock* /app/book-service/

WORKDIR /app/book-service
RUN poetry config virtualenvs.create false && poetry install --no-root

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app

# install pg client for pg_ready
RUN apt-get update && apt-get install -y postgresql-client

COPY --from=builder /usr/local /usr/local

COPY wait-for-db.sh /app/wait-for-db.sh
COPY common/ /app/common
COPY book-service/ /app/book-service

EXPOSE 8000
```

docker-compose.yml:
```yaml
services:
  users_service_db:
    image: postgres
    env_file:
      user-service/.env
    ports:
      - "5434:5432"
    volumes:
      - users_postgres_data:/var/lib/postgresql
    restart: always
    
  books_service_db:
    image: postgres
    env_file:
      book-service/.env
    ports:
      - "5435:5432"
    volumes:
      - books_postgres_data:/var/lib/postgresql
    restart: always

  users_api:
    build: 
      dockerfile: user-service/Dockerfile
      context: .
    env_file:
      user-service/.env
    depends_on:
      - users_service_db
    ports:
      - "8000:8000"
    develop:
      watch:
        - path: ./user-service/user_service
          action: rebuild
          target: /app/user-service
        - path: ./common/common
          action: rebuild
          target: /app/common
    working_dir: /app/user-service
    volumes:
      - ./common:/app/common
      - ./user-service:/app/user-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        uvicorn user_service.main:app --host 0.0.0.0 --port 8000
      "

  books_api:
    build: 
      dockerfile: book-service/Dockerfile
      context: .
    env_file:
      book-service/.env
    depends_on:
      - books_service_db
    ports:
      - "8001:8000"
    develop:
      watch:
        - path: ./book-service/book_service
          action: rebuild
          target: /app/book-service
        
        - path: ./common/common
          action: rebuild
          target: /app/common
    working_dir: /app/book-service
    volumes:
      - ./common:/app/common
      - ./book-service:/app/book-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        uvicorn book_service.main:app --host 0.0.0.0 --port 8000
      "

volumes:
  users_postgres_data:
  books_postgres_data:
```

docker-compose-test.yml:
```yaml
services:
  users_test_db:
    image: postgres:15
    env_file:
      - user-service/.env.test
    ports:
      - "5433:5432"
    tmpfs: # auto clean
      - /var/lib/postgresql/data
    restart: always

  books_test_db:
    image: postgres:15
    env_file:
      - book-service/.env.test
    ports:
      - "5436:5432"
    tmpfs: # auto clean
      - /var/lib/postgresql/data
    restart: always

  users_test:
    build: 
      dockerfile: user-service/Dockerfile
      context: .
    env_file:
      user-service/.env.test
    depends_on:
      - users_test_db
    working_dir: /app/user-service
    volumes:
      - ./common:/app/common
      - ./user-service:/app/user-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        alembic upgrade head &&
        poetry run pytest -v
      "
      
  books_test:
    build: 
      dockerfile: book-service/Dockerfile
      context: .
    env_file:
      book-service/.env.test
    depends_on:
      - books_test_db
    working_dir: /app/book-service
    volumes:
      - ./common:/app/common
      - ./book-service:/app/book-service
    command: >
      sh -c "
        ../wait-for-db.sh &&
        alembic upgrade head &&
        poetry run pytest -v
      "
```

book-service/.env:
```env
# IN REAL PROJECTS .env MUUUUST BE IN .gitignore!!!

POSTGRES_USER=books
POSTGRES_PASSWORD=secret
POSTGRES_HOST=books_service_db
POSTGRES_PORT=5432
POSTGRES_DB=books
```

book-service/.env.test:
```env
POSTGRES_USER=test
POSTGRES_PASSWORD=test
POSTGRES_HOST=books_test_db
POSTGRES_PORT=5432
POSTGRES_DB=test
```


before building the docker compose, don't forgot
to make a lock in book service
```bash
cd book-service
poetry lock
cd ..
docker-compose -f docker-compose.yml up --build --watch
```

You can see that everything is working and if you send a request on a
`http://localhost:8001/books` you will get
```
{
    "status": "ok"
}
```

To work with books table, we need to create it in migrations
```bash
cd book-service/
alembic init migrations
```

book_service/migrations/env.py:
```python
import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool, URL

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def env_database_url() -> URL:
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
    )

    return DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = env_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = env_database_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

create a revision:
```bash
alembic revision -m "create books table"
```

book_service/migrations/versions/4c3d6792331c_create_books_table.py:
```python
"""create books table

Revision ID: 4c3d6792331c
Revises: 
Create Date: 2026-05-08 12:39:00.985100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = '4c3d6792331c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "books",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, index=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("stock", sa.Integer, nullable=False, default=0),
        sa.Column("price", sa.DECIMAL(8, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("books")
```

start the docker compose and run migrations
```bash
docker-compose -f docker-compose.yml up --build --watch
```

```bash
docker-compose exec -it books_api alembic upgrade head
```


Now we are ready to implement routes, services and unit tests
for the books microservice

book_service/routes/books.py:
```python
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from common.core.database import get_db
from book_service.schemas.book import BookCreate, BookOut, BookUpdate
from book_service.services import books as book_service
from book_service.core.logging import logger

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/", response_model=list[BookOut])
async def get_books(db: AsyncSession = Depends(get_db)):
    logger.info("get_books_start")
    try:
        books = await book_service.get_all_books(db)
        logger.info("get_books_success", books_count=len(books))
        return books
    except Exception as e:
        logger.error("get_books_failed", error=str(e))
        raise


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("get_book_start", book_id=book_id)
    try:
        book = await book_service.get_book(book_id, db)
        logger.info("get_book_success", book_id=book_id)
        return book
    except NoResultFound:
        logger.warning("get_book_not_found", book_id=book_id)
        raise HTTPException(status_code=404, detail="Book not found")
    except Exception as e:
        logger.error("get_book_error", book_id=book_id, error=str(e))
        raise HTTPException(status_code=500)


@router.post("/", response_model=BookOut)
async def create_book(data: BookCreate, db: AsyncSession = Depends(get_db)):
    logger.info(
        "create_book_start",
        title=data.title,
        author=data.author,
        stock=data.stock,
        price=data.price,
    )
    try:
        book = await book_service.create_book(data, db)
        logger.info("create_book_success", book_id=book.id)
        return JSONResponse(content=jsonable_encoder(book), status_code=201)
    except Exception as e:
        logger.error("create_book_failed", error=str(e))
        raise


@router.put("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: int, data: BookUpdate, db: AsyncSession = Depends(get_db)
):
    logger.info(
        "update_book_start",
        book_id=book_id,
        title=data.title,
        author=data.author,
        stock=data.stock,
        price=data.price,
    )
    try:
        book = await book_service.update_book(book_id, data, db)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        logger.info("update_book_success", book_id=book_id)
        return book
    except HTTPException:
        logger.warning("update_book_not_found", book_id=book_id)
        raise
    except Exception as e:
        logger.error("update_book_failed", book_id=book_id, error=str(e))
        raise


@router.delete("/{book_id}")
async def delete_book(book_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("delete_book_start", book_id=book_id)
    try:
        await book_service.delete_book(book_id, db)
        logger.info("delete_book_success", book_id=book_id)
        return Response(status_code=204)
    except NoResultFound:
        logger.warning("delete_book_not_found", book_id=book_id)
        raise HTTPException(status_code=404, detail="Book not found")
    except Exception as e:
        logger.error("delete_book_error", book_id=book_id, error=str(e))
        raise HTTPException(status_code=500)
```

book_service/services/books.py:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.exc import NoResultFound

from book_service.models.book import Book
from book_service.schemas.book import BookCreate, BookUpdate
from book_service.core.logging import logger


async def get_all_books(db: AsyncSession):
    logger.debug("service_get_all_books_start")
    result = await db.execute(select(Book))
    books = result.scalars().all()
    logger.debug("service_get_all_books_success", books_count=len(books))
    return books


async def get_book(book_id: int, db: AsyncSession):
    logger.debug("service_get_book_start", book_id=book_id)
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        logger.warning("service_get_book_not_found", book_id=book_id)
        raise NoResultFound()
    logger.debug("service_get_book_success", book_id=book_id)
    return book


async def create_book(data: BookCreate, db: AsyncSession):
    logger.debug(
        "service_create_book_start",
        title=data.title,
        author=data.author,
        stock=data.stock,
        price=data.price,
    )
    try:
        book = Book(**data.model_dump())
        db.add(book)
        await db.commit()
        await db.refresh(book)
        logger.debug("service_create_book_success", book_id=book.id)
        return book
    except Exception as e:
        logger.error("service_create_book_failed", error=str(e))
        raise


async def update_book(book_id: int, data: BookUpdate, db: AsyncSession):
    logger.info(
        "service_update_book_start",
        book_id=book_id,
        title=data.title,
        author=data.author,
        stock=data.stock,
        price=data.price,
    )
    try:
        values = {}
        if data.title is not None:
            values["title"] = data.title
        if data.author is not None:
            values["author"] = data.author
        if data.stock is not None:
            values["stock"] = data.stock
        if data.price is not None:
            values["price"] = data.price

        if not values:
            logger.info("service_update_book_no_fields", book_id=book_id)
            return None

        result = await db.execute(
            update(Book).where(Book.id == book_id).values(**values).returning(Book)
        )
        book = result.scalar_one_or_none()
        await db.commit()

        if not book:
            logger.warning("service_update_book_not_found", book_id=book_id)
            return None

        logger.info("service_update_book_success", book_id=book_id)
        return book
    except Exception as e:
        logger.error("service_update_book_failed", book_id=book_id, error=str(e))
        raise


async def delete_book(book_id: int, db: AsyncSession):
    logger.info("service_delete_book_start", book_id=book_id)
    try:
        result = await db.execute(
            delete(Book).where(Book.id == book_id).returning(Book.id)
        )
        deleted_id = result.scalar_one_or_none()
        await db.commit()

        if deleted_id is None:
            logger.warning("service_delete_book_not_found", book_id=book_id)
            raise NoResultFound()

        logger.info("service_delete_book_success", book_id=book_id)
        return True
    except Exception as e:
        logger.error("service_delete_book_failed", book_id=book_id, error=str(e))
        raise
```

check if everyting is working by sending requests at the `http://localhost:8001/books`

tests folder will look similar to the one from users:
```
.
├── conftest.py
├── __init__.py
├── test_routes
│   └── test_book_routes.py
└── test_services
    └── test_book_service.py
```

book-service/tests/conftest.py:
```python
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from book_service.main import app
from common.core.database import get_db

pytest_plugins = ["common.tests.db_conf"]


# Setup http client
@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://books_test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

book-service/test_services/test_book_service.py:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound
from sqlalchemy import select
from book_service.services import books as book_service
from book_service.schemas.book import BookCreate, BookUpdate
from book_service.models.book import Book


@pytest.mark.anyio
async def test_create_book(db_session: AsyncSession):
    data = BookCreate(title="Dune", author="Frank Herbert", stock=10, price=29.99)
    book = await book_service.create_book(data, db_session)
    assert book.id is not None
    assert book.title == "Dune"
    assert book.author == "Frank Herbert"
    assert book.stock == 10
    assert float(book.price) == 29.99


@pytest.mark.anyio
async def test_create_book_persisted(db_session: AsyncSession):
    data = BookCreate(title="1984", author="George Orwell", stock=5, price=14.99)
    book = await book_service.create_book(data, db_session)
    result = await db_session.execute(select(Book).where(Book.id == book.id))
    db_book = result.scalar_one()
    assert db_book.title == "1984"
    assert db_book.author == "George Orwell"
    assert db_book.stock == 5
    assert float(db_book.price) == 14.99


@pytest.mark.anyio
async def test_get_all_books_empty(db_session: AsyncSession):
    books = await book_service.get_all_books(db_session)
    assert books == []


@pytest.mark.anyio
async def test_get_all_books_multiple(db_session: AsyncSession):
    await book_service.create_book(
        BookCreate(title="Book A", author="Author A", stock=1, price=9.99), db_session
    )
    await book_service.create_book(
        BookCreate(title="Book B", author="Author B", stock=2, price=19.99), db_session
    )
    books = await book_service.get_all_books(db_session)
    assert len(books) == 2


@pytest.mark.anyio
async def test_get_book_success(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Dune", author="Frank Herbert", stock=10, price=29.99),
        db_session,
    )
    fetched = await book_service.get_book(book.id, db_session)
    assert fetched.id == book.id
    assert fetched.title == "Dune"
    assert fetched.author == "Frank Herbert"


@pytest.mark.anyio
async def test_get_book_not_found(db_session: AsyncSession):
    with pytest.raises(NoResultFound):
        await book_service.get_book(999, db_session)


@pytest.mark.anyio
async def test_update_book_full(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Old Title", author="Old Author", stock=1, price=9.99),
        db_session,
    )
    updated = await book_service.update_book(
        book.id,
        BookUpdate(title="New Title", author="New Author", stock=99, price=49.99),
        db_session,
    )
    assert updated.title == "New Title"
    assert updated.author == "New Author"
    assert updated.stock == 99
    assert float(updated.price) == 49.99


@pytest.mark.anyio
async def test_update_book_partial_title(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Old Title", author="Author", stock=5, price=9.99), db_session
    )
    updated = await book_service.update_book(
        book.id, BookUpdate(title="New Title"), db_session
    )
    assert updated.title == "New Title"
    assert updated.author == "Author"
    assert updated.stock == 5
    assert float(updated.price) == 9.99


@pytest.mark.anyio
async def test_update_book_partial_stock(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Title", author="Author", stock=5, price=9.99), db_session
    )
    updated = await book_service.update_book(book.id, BookUpdate(stock=100), db_session)
    assert updated.title == "Title"
    assert updated.stock == 100


@pytest.mark.anyio
async def test_update_book_partial_price(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Title", author="Author", stock=5, price=9.99), db_session
    )
    updated = await book_service.update_book(
        book.id, BookUpdate(price=99.99), db_session
    )
    assert updated.title == "Title"
    assert float(updated.price) == 99.99


@pytest.mark.anyio
async def test_update_book_not_found(db_session: AsyncSession):
    result = await book_service.update_book(999, BookUpdate(title="x"), db_session)
    assert result is None


@pytest.mark.anyio
async def test_update_book_no_fields(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Title", author="Author", stock=5, price=9.99), db_session
    )
    result = await book_service.update_book(
        book.id,
        BookUpdate(),  # empty payload
        db_session,
    )
    assert result is None


@pytest.mark.anyio
async def test_delete_book_success(db_session: AsyncSession):
    book = await book_service.create_book(
        BookCreate(title="Title", author="Author", stock=5, price=9.99), db_session
    )
    result = await book_service.delete_book(book.id, db_session)
    assert result is True
    # verify deletion
    res = await db_session.execute(select(Book).where(Book.id == book.id))
    assert res.scalar_one_or_none() is None


@pytest.mark.anyio
async def test_delete_book_not_found(db_session: AsyncSession):
    with pytest.raises(NoResultFound):
        await book_service.delete_book(999, db_session)
```

book-service/test_routes/test_book_routes.py:
```python
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_route_create_book(client: AsyncClient):
    new_book_data = {
        "title": "Dune",
        "author": "Frank Herbert",
        "stock": 10,
        "price": 29.99,
    }
    response = await client.post("/books/", json=new_book_data)
    data = response.json()
    assert response.status_code == 201
    assert data["title"] == new_book_data["title"]
    assert data["author"] == new_book_data["author"]
    assert data["stock"] == new_book_data["stock"]
    assert float(data["price"]) == new_book_data["price"]
    assert "id" in data


@pytest.mark.anyio
async def test_route_list_all_books(client: AsyncClient):
    new_book_data = {
        "title": "Dune",
        "author": "Frank Herbert",
        "stock": 10,
        "price": 29.99,
    }
    await client.post("/books/", json=new_book_data)
    response = await client.get("/books/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["title"] == new_book_data["title"]
    assert data[0]["author"] == new_book_data["author"]
    assert data[0]["stock"] == new_book_data["stock"]
    assert float(data[0]["price"]) == new_book_data["price"]
    assert "id" in data[0]
    assert "created_at" in data[0]
    assert "updated_at" in data[0]


@pytest.mark.anyio
async def test_route_get_book_by_id(client: AsyncClient):
    new_book_data = {
        "title": "1984",
        "author": "George Orwell",
        "stock": 5,
        "price": 14.99,
    }
    create_response = await client.post("/books/", json=new_book_data)
    new_book = create_response.json()
    response = await client.get(f"/books/{new_book['id']}")
    data = response.json()
    assert response.status_code == 200
    assert data["title"] == new_book_data["title"]
    assert data["author"] == new_book_data["author"]
    assert data["stock"] == new_book_data["stock"]
    assert float(data["price"]) == new_book_data["price"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.anyio
async def test_route_get_book_by_id_not_found(client: AsyncClient):
    response = await client.get("/books/999")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_book(client: AsyncClient):
    new_book_data = {
        "title": "Old Title",
        "author": "Old Author",
        "stock": 3,
        "price": 9.99,
    }
    create_response = await client.post("/books/", json=new_book_data)
    new_book = create_response.json()
    response = await client.put(
        f"/books/{new_book['id']}",
        json={
            "title": "New Title",
            "author": "New Author",
            "stock": 99,
            "price": 49.99,
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert data["title"] == "New Title"
    assert data["author"] == "New Author"
    assert data["stock"] == 99
    assert float(data["price"]) == 49.99


@pytest.mark.anyio
async def test_update_book_not_found(client: AsyncClient):
    response = await client.put("/books/999", json={"title": "x"})
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_book(client: AsyncClient):
    new_book_data = {
        "title": "Dune",
        "author": "Frank Herbert",
        "stock": 10,
        "price": 29.99,
    }
    create_response = await client.post("/books/", json=new_book_data)
    new_book = create_response.json()
    response = await client.delete(f"/books/{new_book['id']}")
    assert response.status_code == 204
    # ensure it's gone
    response = await client.get(f"/books/{new_book['id']}")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_book_not_found(client: AsyncClient):
    response = await client.delete("/books/999")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_book_invalid_payload(client: AsyncClient):
    # missing required fields
    response = await client.post("/books/", json={"title": "Only Title"})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_book_invalid_types(client: AsyncClient):
    response = await client.post(
        "/books/",
        json={"title": 123, "author": "Author", "stock": "not-an-int", "price": "free"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_update_partial_title(client: AsyncClient):
    new_book_data = {"title": "Original", "author": "Author", "stock": 5, "price": 9.99}
    create_response = await client.post("/books/", json=new_book_data)
    new_book = create_response.json()
    response = await client.put(
        f"/books/{new_book['id']}", json={"title": "Updated Title"}
    )
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["author"] == "Author"
    assert data["stock"] == 5
    assert float(data["price"]) == 9.99


@pytest.mark.anyio
async def test_update_partial_stock(client: AsyncClient):
    new_book_data = {"title": "Title", "author": "Author", "stock": 5, "price": 9.99}
    create_response = await client.post("/books/", json=new_book_data)
    new_book = create_response.json()
    response = await client.put(f"/books/{new_book['id']}", json={"stock": 50})
    data = response.json()
    assert data["title"] == "Title"
    assert data["stock"] == 50
    assert float(data["price"]) == 9.99
```

run the tests and check if they are passing
```bash
docker-compose -f docker-compose-test.yml run --rm books_test
```

## Kubernetes configuration

We have created 2 microservices and development environment for it.
To deploy it in production you have to use container orchestraion tool.
We will configure kubernetes because it allows for easy scaling of microservices.

I expect some basic knowledge about k8s from you before we begin.

I don't want to buy vps so I will use `minikube` to test
everything. You can also install it on yor machine and use as a 
kubernetes node.

It is possible to configure everyting only with terminal
but I like to keep everything in code so I will create
yaml manifests.

Create `k8s` folder in root of the project.
The final structure will look like that:
```
.
├── api_ingress.yml
├── book
│   ├── book_postgres_deploy.yml
│   ├── book_postgres_pvc.yml
│   ├── book_postgres_secret.yml
│   ├── book_postgres_service.yml
│   ├── books_deploy.yml
│   └── books_service.yml
└── user
    ├── user_postgres_deploy.yml
    ├── user_postgres_pvc.yml
    ├── user_postgres_secret.yml
    ├── user_postgres_service.yml
    ├── users_deploy.yml
    └── users_service.yml
```

before we start I want to quickly explain the difference between
k8s resources that are going to be implemented.

- Deployment - manages and runs the container
- Service - exposes container and basically provide a way to connect with them
- Ingress - exposes services to outside world so we are able to connect without logging inside node
- PersistentVolumeClaim - similar to the volume in docker compose. Persistent storage for any kind of data
- Secret - kind of .env. Any secret data that you want to pass into the environment variables


Let's start with postgres database:

k8s/user/user_postgres_deploy.yml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: users-postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: users-postgres
  template:
    metadata:
      labels:
        app: users-postgres
    spec:
      containers:
      - name: users-postgres
        image: postgres:16
        args:
          - postgres
          - -c
          - max_prepared_transactions=1000
        envFrom:
          - secretRef:
              name: users-db-secret
        ports:
          - containerPort: 5432
        resources:
          limits:
            memory: "128Mi"
            cpu: "500m"
        volumeMounts:
          - name: postgres-storage
            mountPath: /var/lib/postgresql/data
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "postgres"]
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
        - name: postgres-storage
          persistentVolumeClaim:
            claimName: users-postgres-pvc
```

k8s/user/user_postgres_pvc.yml:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: users-postgres-pvc
spec:
  resources:
    requests:
      storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce
```

k8s/user/user_postgres_secret.yml:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: users-db-secret
type: Opaque
stringData:
  POSTGRES_USER: users
  POSTGRES_PASSWORD: secret
  POSTGRES_DB: users
  POSTGRES_HOST: users-db-service
  POSTGRES_PORT: "5432"
```

k8s/user/user_postgres_service.yml:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: users-db-service
spec:
  selector:
    app: users-postgres
  ports:
  - port: 5432
    targetPort: 5432
```


here is fastapi app manifests:

k8s/user/users_deploy.yml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: users-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: users-api
  template:
    metadata:
      labels:
        app: users-api
    spec:
      initContainers:
        - name: run-migrations
          image: misha654/purchase-users-api:latest
          workingDir: /app/user-service
          command:
            - sh
            - -c
            - |
              until pg_isready -h users-db-service -U users; do
                echo "Waiting for db..."
                sleep 1
              done
              alembic upgrade head
          envFrom:
            - secretRef:
                name: users-db-secret
      containers:
      - name: users-api
        image: misha654/purchase-users-api:latest
        workingDir: /app/user-service
        command:
          - uvicorn
          - user_service.main:app
          - --host
          - "0.0.0.0"
          - --port
          - "8000"
        envFrom:
          - secretRef:
              name: users-db-secret
        resources:
          limits:
            memory: "128Mi"
            cpu: "500m"
        ports:
        - containerPort: 8000
```

k8s/user/users_service.yml:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: users-api-service
spec:
  selector:
    app: users-api
  ports:
  - port: 8000
    targetPort: 8000
```


Now book service:

k8s/book/book_postgres_deploy.yml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: books-postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: books-postgres
  template:
    metadata:
      labels:
        app: books-postgres
    spec:
      containers:
      - name: books-postgres
        image: postgres:16
        args:
          - postgres
          - -c
          - max_prepared_transactions=1000
        envFrom:
          - secretRef:
              name: books-db-secret
        ports:
          - containerPort: 5432
        resources:
          limits:
            memory: "128Mi"
            cpu: "500m"
        volumeMounts:
          - name: postgres-storage
            mountPath: /var/lib/postgresql/data
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "postgres"]
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
        - name: postgres-storage
          persistentVolumeClaim:
            claimName: books-postgres-pvc
```

k8s/book/book_postgres_pvc.yml:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: books-postgres-pvc
spec:
  resources:
    requests:
      storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce
```

k8s/book/book_postgres_secret.yml:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: books-db-secret
type: Opaque
stringData:
  POSTGRES_USER: books
  POSTGRES_PASSWORD: secret
  POSTGRES_DB: books
  POSTGRES_HOST: books-db-service
  POSTGRES_PORT: "5432"
```

k8s/book/book_postgres_service.yml:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: books-db-service
spec:
  selector:
    app: books-postgres
  ports:
  - port: 5432
    targetPort: 5432
```

k8s/book/books_deploy.yml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: books-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: books-api
  template:
    metadata:
      labels:
        app: books-api
    spec:
      initContainers:
        - name: run-migrations
          image: misha654/purchase-books-api:latest
          workingDir: /app/book-service
          command:
            - sh
            - -c
            - |
              until pg_isready -h books-db-service -U books; do
                echo "Waiting for db..."
                sleep 1
              done
              alembic upgrade head
          envFrom:
            - secretRef:
                name: books-db-secret
      containers:
      - name: books-api
        image: misha654/purchase-books-api:latest
        workingDir: /app/book-service
        command:
          - uvicorn
          - book_service.main:app
          - --host
          - "0.0.0.0"
          - --port
          - "8000"
        envFrom:
          - secretRef:
              name: books-db-secret
        resources:
          limits:
            memory: "128Mi"
            cpu: "500m"
        ports:
        - containerPort: 8000
```

k8s/book/books_service.yml:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: books-api-service
spec:
  selector:
    app: books-api
  ports:
  - port: 8000
    targetPort: 8000
```

Finally we need to add ingress to expose services

k8s/api_ingress.yml:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  labels:
    app.kubernetes.io/name: api-ingress
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
        - pathType: Prefix
          path: "/users"
          backend:
            service:
              name: users-api-service
              port: 
                number: 8000
        - pathType: Prefix
          path: "/books"
          backend:
            service:
              name: books-api-service
              port: 
                number: 8000
```

start minikube and enable ingress (skip if you are using real vps):
```bash
minikube start
minikube addons enable ingress
```

To apply every manifest use:
```bash
kubectl apply -f k8s/ -R
```

if you create everything (including ingress) first time you can get
error related to internal minikube ingress webhook. Just run apply one more time.

you can check if all pods are created with
```bash
kubectl get pod
```

if everything is good, let's try to send some requests.

Get the minikube ip on your machine:
```bash
minikube ip
```

try to send some requests at
```
http://192.168.49.2/users
http://192.168.49.2/books
```

Let's try to make more replicas of our microservices:
```bash
kubectl scale deployment books-api --replicas 3
kubectl scale deployment users-api --replicas 3
```

now you can check that every microservice have 3 pods:
```bash
kubectl get pod
```

try to send some requests at to check if everything is good
```
http://192.168.49.2/users
http://192.168.49.2/books
```



Everything seems to work fine!
Congrats! you just created 2 microservices, deployed and scaled it with kubernetes

Hope you that tutorial was helpful