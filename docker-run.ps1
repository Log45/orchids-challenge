# Stop any existing containers with the same name
Write-Host "Stopping any existing containers..." -ForegroundColor Yellow
docker stop orchids-challenge 2>$null
docker rm orchids-challenge 2>$null

# Build the Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t orchids-challenge .

# Check if build was successful
if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful!" -ForegroundColor Green
    
    # Run the container
    Write-Host "Starting container..." -ForegroundColor Yellow
    docker run -d `
        --name orchids-challenge `
        -p 3000:3000 `
        -p 8000:8000 `
        -v ${PWD}/cloned_site:/app/cloned_site `
        orchids-challenge

    # Check if container started successfully
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Container started successfully!" -ForegroundColor Green
        Write-Host "Frontend is available at: http://localhost:3000" -ForegroundColor Cyan
        Write-Host "Backend is available at: http://localhost:8000" -ForegroundColor Cyan
        
        # Show container logs
        Write-Host "`nContainer logs:" -ForegroundColor Yellow
        docker logs -f orchids-challenge
    } else {
        Write-Host "Failed to start container!" -ForegroundColor Red
    }
} else {
    Write-Host "Build failed!" -ForegroundColor Red
} 