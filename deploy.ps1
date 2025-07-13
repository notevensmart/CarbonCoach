param(
    [string]$CommitMessage = "Update and deploy"
)

git add .

git commit -m "$CommitMessage"

git push

docker build -t us-central1-docker.pkg.dev/carboncoach-465605/carboncoach-repo/carboncoach .

docker push us-central1-docker.pkg.dev/carboncoach-465605/carboncoach-repo/carboncoach
gcloud run deploy carboncoach --image us-central1-docker.pkg.dev/carboncoach-465605/carboncoach-repo/carboncoach --platform managed --region us-central1 --allow-unauthenticated --set-env-vars "OPENROUTER_API_KEY=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,CLIMATIQ_API_KEY=SCCDV0RCQD1AV7RN7SA3P8RDAR"


