import io
import torch
import torch.nn as nn
from fastapi import FastAPI, HTTPException
from torchvision import models, transforms
from PIL import Image
import uvicorn

app = FastAPI(title="AI QC Service")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = models.convnext_base(weights=None)
model.classifier = nn.Sequential(
    nn.AdaptiveAvgPool2d((1, 1)),
    nn.Flatten(),
    nn.BatchNorm1d(1024),
    nn.Linear(1024, 512),
    nn.ReLU(),
    nn.Dropout(0.4),
    nn.Linear(512, 2)
)

# Load weights
load_path = "0.77963-best_model_epoch15_f193.90_loss0.1541.pth"
try:
    model.load_state_dict(torch.load(load_path, map_location=device))
    model.to(device)
    model.eval()
    print(f"Model loaded successfully on {device}")
except FileNotFoundError:
    print(f"Warning: {load_path} not found. Running with random weights.")

# Preprocessing Pipeline
preprocess = transforms.Compose([
    transforms.Resize(232),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

@app.post("/requests/{request_id}/qc/run")
async def run_qc(request_id: str):
    """
    Endpoint triggered by your ApiClient.run_qc(request_id)
    """
    try:
        image_path = "download.png" 
        
        img = Image.open(image_path).convert('RGB')
        img_tensor = preprocess(img).unsqueeze(0).to(device)

        with torch.no_grad():
            output = model(img_tensor)
            probabilities = torch.nn.functional.softmax(output[0], dim=0)
        
        labels = ["Real", "AI Generated"]
        conf, pred_idx = torch.max(probabilities, 0)
        
        return {
            "request_id": request_id,
            "status": "completed",
            "label": labels[pred_idx.item()],
            "confidence": round(conf.item(), 4)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)