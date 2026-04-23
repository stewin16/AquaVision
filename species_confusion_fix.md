# 🔬 Fixing Species Confusion in AquaVision — Deep Research Report

## The Problem

Your YOLO models confuse **similar-looking species** and **juvenile/baby versions** of fish. With **65 classes** including visually similar pairs like:

| Confuser Pair | Why it's Hard |
|---|---|
| Black Pomfret ↔ Pomfret | Same shape, color difference is subtle |
| Rohu ↔ Indian Carp ↔ Catla | All large silver carps, juveniles look identical |
| Puti ↔ Shorputi | Nearly identical except size |
| Red Mullet ↔ Striped Red Mullet | Same family, minor pattern difference |
| Parrotfish ↔ Bumphead Parrotfish | Same family, size/shape variation |
| Grouper ↔ Humpback Grouper | Same family, different markings |

Your current setup:
- **model.tflite** (22MB) — Standard/Small model for captures
- **model_nano.tflite** (6MB) — Fast Nano model for preview  
- Confidence threshold: **0.4** | IoU threshold: **0.7**

---

## Offline Solutions (Ranked by Impact vs Effort)

### 🏆 Strategy 1: Two-Stage Pipeline (BEST for your case)

> [!IMPORTANT]
> This is the **#1 recommended approach** — YOLO detects "fish", then a lightweight classifier identifies the species from the crop.

**How it works:**
```
Camera Frame → YOLO (detect fish boxes) → Crop each box → EfficientNet-Lite (classify species)
```

**Why this works so well:**
- YOLO is great at **locating** objects but mediocre at **fine-grained classification** (65 classes with similar features)
- A classifier like EfficientNet-Lite gets the **entire cropped fish** as input (no background noise) and is purpose-built for distinguishing subtle differences

**Implementation plan:**

1. **Merge similar classes in YOLO** → Train YOLO to detect just `"Fish"`, `"Crab"`, `"Shrimp"`, `"Turtle"`, etc. (reduce to ~8-10 super-classes)
2. **Train EfficientNet-Lite0** on cropped fish images for the 65 species
3. **Pipeline in Android:**
   ```kotlin
   // After YOLO detects boxes:
   for (box in boundingBoxes) {
       val crop = Bitmap.createBitmap(frame, box.x1, box.y1, box.w, box.h)
       val species = speciesClassifier.classify(crop) // EfficientNet-Lite
       box.clsName = species.label
       box.cnf = species.confidence
   }
   ```

**Model sizes:**
| Model | Size | Speed (mobile) |
|---|---|---|
| EfficientNet-Lite0 (INT8) | **~5MB** | ~15ms per crop |
| EfficientNet-Lite1 (INT8) | **~8MB** | ~25ms per crop |
| MobileNetV3-Small (INT8) | **~3MB** | ~8ms per crop |

**Tools to train:**
- [TensorFlow Lite Model Maker](https://www.tensorflow.org/lite/models/modify/model_maker/image_classification) — easiest
- [Ultralytics classify](https://docs.ultralytics.com/tasks/classify/) — `yolo classify train`
- Custom PyTorch → export to TFLite

---

### 🥈 Strategy 2: Raise Confidence + Tune NMS (Quick Win, No Retraining)

> [!TIP]
> This is a **zero-effort fix** you can do right now in `Detector.kt`.

**Current values:**
```kotlin
CONFIDENCE_THRESHOLD = 0.4F  // Too low — accepts uncertain guesses
IOU_THRESHOLD = 0.7F         // Too high — allows overlapping boxes
```

**Recommended tuning:**
```kotlin
CONFIDENCE_THRESHOLD = 0.55F  // Only accept confident predictions
IOU_THRESHOLD = 0.5F          // Suppress overlapping boxes more aggressively
```

**Why this helps:**
- At 0.4 confidence, the model outputs its "best guess" even when it's 40% sure — leading to wrong species labels
- At 0.55+, only high-confidence detections pass through, drastically reducing misclassifications
- Lower IoU threshold means if two boxes overlap significantly, the weaker (often wrong) one gets removed

**Tradeoff:** You might miss a few low-confidence but correct detections. But for species ID accuracy, **precision > recall**.

---

### 🥉 Strategy 3: Confusion Matrix + Targeted Data Fixes

**Step 1:** Generate a confusion matrix from your validation data:
```python
from ultralytics import YOLO
model = YOLO("best.pt")
results = model.val(data="fish.yaml", conf=0.5)
# This auto-generates confusion_matrix.png
```

**Step 2:** Identify the top confused pairs and fix them:

| Fix | How |
|---|---|
| **More data for confused species** | Collect 200+ extra images specifically of the confused pairs |
| **Harder augmentations** | Use CutMix, Mosaic, color jitter to force the model to learn fine details |
| **Tighter bounding boxes** | Re-annotate to have tight crops (no excess background) |
| **Higher resolution training** | Train at 640×640 instead of 320/416 — fine details are preserved |

---

### Strategy 4: Soft-NMS (Replace Hard NMS)

Your current `applyNMS()` uses **hard NMS** — it completely removes overlapping boxes. This can suppress valid detections of similar fish near each other.

**Soft-NMS** instead *decays* confidence scores of overlapping boxes:

```kotlin
// In Detector.kt, replace applyNMS with:
private fun applySoftNMS(boxes: List<BoundingBox>, sigma: Float = 0.5f): List<BoundingBox> {
    val sorted = boxes.sortedByDescending { it.cnf }.toMutableList()
    val selected = mutableListOf<BoundingBox>()
    
    while (sorted.isNotEmpty()) {
        val best = sorted.removeAt(0)
        selected.add(best)
        
        val iterator = sorted.listIterator()
        while (iterator.hasNext()) {
            val box = iterator.next()
            val iou = calculateIoU(best, box)
            // Gaussian decay instead of hard removal
            val decayedConf = box.cnf * Math.exp(-(iou * iou) / sigma).toFloat()
            if (decayedConf < CONFIDENCE_THRESHOLD) {
                iterator.remove()
            } else {
                iterator.set(box.copy(cnf = decayedConf))
            }
        }
    }
    return selected
}
```

---

### Strategy 5: Knowledge Distillation (For Better Nano Model)

If you have a large, accurate model on PC:
1. Train a big **YOLOv8-Large** or **YOLOv8-XLarge** teacher model
2. Use it to generate "soft labels" for your training data
3. Train your Nano student model using these soft labels

The student learns the teacher's nuanced probability distributions, not just hard class labels — making it better at borderline cases.

---

### Strategy 6: Hierarchical Classification (In-App Logic)

Without retraining, add **in-app heuristic rules** for known confuser pairs:

```kotlin
// In CameraFragment, after detection:
fun resolveConfusedSpecies(box: BoundingBox, allBoxes: List<BoundingBox>): String {
    return when {
        // If Puti detected with low confidence AND fish is large → likely Shorputi
        box.clsName == "Puti" && box.cnf < 0.65 && box.h > 0.3 -> "Shorputi"
        
        // If Pomfret AND fish is dark → likely Black Pomfret
        box.clsName == "Pomfret" && box.cnf < 0.6 -> "Black Pomfret"
        
        // If multiple carps detected, keep only highest confidence
        box.clsName in listOf("Rohu", "Catla", "Indian Carp") && box.cnf < 0.55 -> {
            val bestCarp = allBoxes
                .filter { it.clsName in listOf("Rohu", "Catla", "Indian Carp") }
                .maxByOrNull { it.cnf }
            bestCarp?.clsName ?: box.clsName
        }
        
        else -> box.clsName
    }
}
```

---

## Recommended Action Plan

| Priority | Action | Effort | Impact |
|---|---|---|---|
| **🔴 Do Now** | Raise confidence to 0.55, lower IoU to 0.5 | 5 min | Medium |
| **🔴 Do Now** | Add Soft-NMS to `Detector.kt` | 30 min | Medium |
| **🟡 This Week** | Generate confusion matrix, identify worst pairs | 2 hrs | High (diagnostic) |
| **🟡 This Week** | Add hierarchical heuristic rules for known confusers | 1 hr | Medium |
| **🟢 Next Sprint** | Train EfficientNet-Lite0 second-stage classifier | 1-2 days | **Very High** |
| **🟢 Next Sprint** | Retrain YOLO with super-classes + more data | 2-3 days | **Very High** |

> [!CAUTION]
> The two-stage pipeline (Strategy 1) is the gold standard for this problem, but it requires collecting a curated dataset of cropped species images and training a new model. The quick wins (Strategies 2, 4, 6) can be deployed **today** with code-only changes.

---

## Useful Datasets for Retraining

| Dataset | Species | Images | Link |
|---|---|---|---|
| **FishNet (ICCV 2023)** | 17,357 species | 94,532 | [fishnet-2023.github.io](https://fishnet-2023.github.io/) |
| **Fishnet.ai** | Tuna/commercial | Large-scale | [fishnet.ai](https://fishnet.ai/) |
| **WildFish++** | Wild fish | Large | GitHub |
| **Roboflow Fish Datasets** | Various | 1K-10K | [roboflow.com/universe](https://universe.roboflow.com/) |

## Tools for Offline Mobile Classifiers

| Tool | Best For | Output |
|---|---|---|
| **TF Lite Model Maker** | Quick image classifier training | `.tflite` |
| **Ultralytics classify** | YOLO-family classifier | `.tflite` / `.onnx` |
| **PyTorch → ONNX → TFLite** | Custom architectures | `.tflite` |
| **MediaPipe Model Maker** | Google's latest, best Android support | `.tflite` with metadata |
