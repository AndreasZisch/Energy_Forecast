# 🏗️ Architecture Decision Records (ADR) Log

This document captures the key architectural decisions made for the **Distributed AI Energy Grid** project, including the context, the decision itself, and the consequences (trade-offs).

## 📋 Table of Contents
* [ADR-001: Microservices Architecture Style](#adr-001-microservices-architecture-style)
* [ADR-002: Carbon-Aware Dynamic Orchestration](#adr-002-carbon-aware-dynamic-orchestration)
* [ADR-003: Offline Training with Baked Artifacts](#adr-003-offline-training-with-baked-artifacts)
* [ADR-004: Emergency Static Fallback (Circuit Breaker)](#adr-004-emergency-static-fallback-circuit-breaker)
* [ADR-005: Dynamic Infrastructure Scaling (Green Redeployment)](#adr-005-dynamic-infrastructure-scaling-green-redeployment)
---

## ADR-001: Microservices Architecture Style

### 1. Status
**Accepted**

### 2. Context
The system needs to integrate multiple distinct components: a user interface, a heavy AI model (XGBoost), a lightweight AI model (Holt-Winters), and a routing logic.
* A **Monolithic** approach would bundle all dependencies (heavy Machine Learning libraries vs. lightweight Web libraries) into one massive runtime.
* If the heavy model crashes due to memory issues in a monolith, it risks taking down the UI and the lightweight model with it.

### 3. Decision
We decided to adopt a **Microservices Architecture**, separating the system into four distinct Docker containers:
1.  **Frontend:** Streamlit GUI (Visuals only).
2.  **Gateway:** FastAPI Orchestrator (Routing logic).
3.  **Service A:** XGBoost Predictor (Heavy compute).
4.  **Service B:** Holt-Winters Predictor (Lightweight compute).

### 4. Consequences
* **✅ Positive:**
    * **Fault Isolation:** If `Service A` crashes, the GUI and `Service B` remain operational.
    * **Independent Scaling:** We can scale the Orchestrator separately from the heavy compute nodes.
    * **Tech Stack Freedom:** Different services can use different Python versions or libraries without dependency conflicts.
* **❌ Negative:**
    * **Complexity:** Requires container orchestration (Kubernetes/Docker Compose) and service discovery logic.
    * **Latency:** Introduces network hops (HTTP) between the Orchestrator and the Models.

---

## ADR-002: Carbon-Aware Dynamic Orchestration

### 1. Status
**Accepted**

### 2. Context
Traditional forecasting systems prioritize accuracy above all else, ignoring the energy cost of computation. Our project requirement is to implement "Green AI"—software that adapts its behavior to minimize carbon footprint. We need a way to choose between models dynamically based on environmental conditions.

### 3. Decision
We implemented a **Distributed Orchestrator Pattern** combined with a **Virtual Carbon Sensor**.
* The Orchestrator acts as a supervisory system. Before every request, it queries the Carbon Simulator.
* **Logic:**
    * If Grid Carbon < Threshold (`LOW`): Route to **XGBoost**.
    * If Grid Carbon > Threshold (`HIGH`): Route to **Holt-Winters**.

### 4. Consequences
* **✅ Positive:**
    * **Sustainability:** Drastically reduces energy consumption during dirty grid hours (Holt-Winters uses ~90% less CPU than XGBoost).
    * **Adaptability:** The system reacts to real-time external factors (simulated grid data).
* **❌ Negative:**
    * **Accuracy Trade-off:** During "High Carbon" windows, we knowingly provide a slightly less accurate forecast to save energy.
    * **Overhead:** Adds an extra API call (to the sensor) before every prediction.

---

## ADR-003: Offline Training with Baked Artifacts

### 1. Status
**Accepted**

### 2. Context
Machine Learning models require training (learning from data) and inference (predicting).
* **Online (Real-time) training** provides the freshest data but is computationally expensive, slow, and energy-intensive.
* The system needs to respond to User Interface requests in milliseconds.

### 3. Decision
We decided to separate the **Training Phase** from the **Inference Phase**.
* **Training:** Performed offline using historical 2024 ENTSO-E data. The resulting model files (`.json`, `.pkl`) are serialized.
* **Deployment:** These pre-trained artifacts are "baked" directly into the Docker images during the build process.
* **Runtime:** The containers load the models into RAM at startup.

### 4. Consequences
* **✅ Positive:**
    * **Performance:** Inference is near-instant (<50ms) as no training happens during the request.
    * **Stability:** We guarantee that the model running in production is the exact same one verified during development.
* **❌ Negative:**
    * **Staleness:** The models do not learn from new data entering the system automatically. They must be manually retrained and redeployed to update their knowledge.

---

## ADR-004: Emergency Static Fallback (Circuit Breaker)

### 1. Status
**Accepted**

### 2. Context
In a distributed system, network failures, container crashes, or timeouts are inevitable.
* If the Orchestrator cannot reach either the XGBoost service OR the Holt-Winters service, the standard behavior would be to return an HTTP 500 Error.
* This would cause the Frontend (Streamlit) to crash or show an ugly traceback to the user.

### 3. Decision
We implemented a **Static Fallback Mechanism** (Emergency Mode) inside the API Gateway.
* If **all** downstream microservices fail (throw exceptions), the Gateway catches the error.
* It generates a mathematically safe "dummy" forecast (e.g., flat zeros or average values) for the next 24 hours.
* It tags the response metadata with `status: Emergency Mode`.

### 4. Consequences
* **✅ Positive:**
    * **High Availability:** The User Interface *never* breaks. The user always sees a valid page, even if the backend is burning.
    * **User Experience:** Clear feedback via metadata allows the UI to show a "System Warning" badge instead of a generic error.
* **❌ Negative:**
    * **Data Validity:** The data shown during an outage is synthetic and factually incorrect (though safe). Users might mistake it for a real prediction if they ignore the warning.

---

## ADR-005: Dynamic Infrastructure Scaling (Green Redeployment)

### 1. Status
**Accepted**

### 2. Context
Merely routing traffic away from the heavy **XGBoost Service** during "High Carbon" periods is insufficient for true sustainability. If the container remains running in the background (idle), it continues to consume RAM and CPU cycles, contributing to "Zombie Infrastructure" emissions.
* To achieve true **Green AI**, the system must physically release computing resources when they are not environmentally viable.

### 3. Decision
We implemented **Active Lifecycle Management** within the Decision Logic (Orchestrator).
* **Mechanism:** The Orchestrator communicates directly with the infrastructure runtime (Docker Socket).
* **Behavior:**
    * **High Carbon Event:** The system sends a `scale --replicas=0` command to the XGBoost Deployment, terminating the container.
    * **Low Carbon Event:** The system sends a `scale --replicas=1` command to restart the XGBoost container.

### 4. Consequences
* **✅ Positive:**
    * **Zero Idle Waste:** This ensures absolute minimum energy usage during dirty grid windows. The hardware resources are freed up for other tasks or allowed to idle down.
    * **Educational Value:** Demonstrates advanced "Infrastructure as Code" control driven by environmental sensors.
* **❌ Negative:**
    * **Cold Start Latency:** When the grid turns "Green" again, the first user request will experience a delay (5-10 seconds) while the XGBoost container boots up and loads the model into memory.
    * **Complexity:** Requires the Orchestrator container to have elevated privileges (`ServiceAccount` or `Docker Socket` access) to manage other containers.