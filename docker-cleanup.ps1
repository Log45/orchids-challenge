# Stop and remove the container
Write-Host "Stopping and removing container..." -ForegroundColor Yellow
docker stop orchids-challenge 2>$null
docker rm orchids-challenge 2>$null

# Remove the image
Write-Host "Removing Docker image..." -ForegroundColor Yellow
docker rmi orchids-challenge 2>$null

# Clean up any dangling images
Write-Host "Cleaning up dangling images..." -ForegroundColor Yellow
docker image prune -f

Write-Host "Cleanup complete!" -ForegroundColor Green 