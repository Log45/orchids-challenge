# Orchids SWE Intern Challenge Template

This project consists of a backend built with FastAPI and a frontend built with Next.js and TypeScript.

## Windows Users

The backend uses HyperBrowser.ai and playwright, which depend on Python's `asyncio` package when run as part of a webapp. Due to compatibility issues with Windows machines, this feature does not work as expected. Because of that, I created a Dockerfile to containerize the frontend and backend together, which allows Windows users to run the app.

### Instructions

First, open Docker Desktop, or start a docker engine through powershell, then ensure you are in the project's root directory. 

```bash
.\docker-run.ps1 # run the powershell script to run the docker container
# Alternatively, run the following commands (if you are on Unix systems then you cannot run the .ps1 script)
docker build -t orchids-challenge .
docker run -d --name orchids-challenge -p 3000:3000 -p 8000:8000 -v ${PWD}/cloned_site:/app/cloned_site orchids-challenge
```

After you're done, make sure to stop and remove the docker images. You can do so by running `.\docker-cleanup.ps1`


## Backend

The backend uses `uv` for package management.

### Installation

To install the backend dependencies, run the following command in the backend project directory:

```bash
uv sync
```

### Running the Backend

To run the backend development server, use the following command:

```bash
uv run fastapi dev
```

## Frontend

The frontend is built with Next.js and TypeScript.

### Installation

To install the frontend dependencies, navigate to the frontend project directory and run:

```bash
npm install
```

### Running the Frontend

To start the frontend development server, run:

```bash
npm run dev
```
