# AI Forecasting for Renewable Energy Output (Wind & Solar)

**Team Members:**  
- Andreas Zisch  
- Apurba Bhushan Parajuli 

## 1. Project Definition
The **AI Forecasting for Renewable Energy** is a cloud-native, microservice-based forecasting system designed to predict renewable energy generation (Solar, Wind) across Europe. It relies on AI models trained offline using **2024 historical data sourced directly from the ENTSO-E Transparency Platform via API**.

Unlike traditional forecasting tools, this system implements **"Green Intelligence"**: it dynamically shifts its computational load between heavy, high-accuracy models (XGBoost) and lightweight, eco-friendly models (Holt-Winters) based on the real-time carbon intensity of the electricity grid.

---

## 2. Project Description
As AI models grow larger, their energy consumption and carbon footprint have become a critical concern. This project serves as a **proof-of-concept for Sustainable AI**, demonstrating how software architecture can actively contribute to decarbonization.

### **How it handles Data & Compute**
To ensure reliability and low latency, the system separates **Offline Training** from **Online Inference**.
* **Data Foundation:** The models are trained on raw CSV datasets containing hourly generation data for 2024, downloaded via the ENTSO-E API.
* **Pre-Baked Intelligence:** Training happens locally to isolate the heavy energy cost. The pre-trained model artifacts are then "baked" into the Docker containers, allowing the live system to perform millisecond-level inference without the overhead of retraining.

### **The "Green" Logic**
The system functions as a distributed grid of intelligent agents. A central **Orchestrator** acts as the brain, constantly monitoring a **Virtual Carbon Sensor**.

* **When the grid is "Green" (Low Carbon):** The system routes requests to the computationally intensive **XGBoost Service** (Container A) to maximize forecast accuracy.
* **When the grid is "Dirty" (High Carbon):** The system automatically downgrades to the lightweight **Holt-Winters Service** (Container B), sacrificing negligible accuracy to reduce computational energy usage by over 90%.

Built on a robust **Docker-Compose or Kubernetes** infrastructure, the application features automatic failover, self-healing capabilities, and a decoupled **Streamlit GUI** that allows users to interact with the system and visualize the "Carbon vs. Accuracy" trade-off in real-time.

**UML Diagram**
![UML Diagram](https://github.com/Apurba1001/AI-Forecasting-for-Renewable-Energy-/blob/Andreas/diagrams/UML%20Diagram.jpg)
---

## 3. Key Features
* **🌱 Carbon-Aware Orchestration:** Automatically switches between AI models based on simulated live grid carbon intensity.
* **🏗️ Microservices Architecture:** Fully decoupled services (API Gateway, GUI, Model A, Model B) deployed via Docker and Docker-Compose/Kubernetes.
* **🔄 High Availability & Failover:** If the primary AI service fails, the Orchestrator instantly re-routes traffic to the fallback model without user interruption.
* **🛡️ Emergency Static Mode:** A "Doomsday" protocol that generates safe static data if all intelligence services go offline, preventing frontend crashes.
* **📊 Interactive Dashboard:** A Streamlit interface for visualizing generation mix (Solar/Wind) and monitoring system health.

---

## 4. System Architecture

* **Frontend:** Streamlit (Python) - *Visualization & User Input*
* **Gateway:** FastAPI - *Routing & Traffic Control*
* **Intelligence:** Orchestrator & Carbon Simulator
* **Compute Nodes:**
    * **Node A:** XGBoost (Gradient Boosting) - *High Accuracy / High Cost*
    * **Node B:** Holt-Winters (Exponential Smoothing) - *Fast / Low Cost*

---

## 5. Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.9+ |
| **Web Framework** | FastAPI |
| **Data Science** | Pandas, XGBoost, Statsmodels |
| **Sustainability** | CodeCarbon (Real-time footprint tracking) |
| **Containerization** | Docker & Docker Compose |
| **Frontend** | Streamlit |

---

## 6. How It Works (The Logic Flow)
1. **User** selects a country (e.g., Germany) in the GUI.
2. **API Gateway** receives the request and asks the **Carbon Simulator**: *"Is the grid green right now?"*
3. **Decision Logic:**
    * ✅ **YES:** Call `XGBoost Service` (Container 1).
    * ❌ **NO:** Call `Holt-Winters Service` (Container 2).
4. **Failover:** If the chosen service is down, the system immediately tries the other one.
5. **Response:** The user sees the forecast chart along with the **CO2 footprint** of that specific calculation.

---

## 7. Architecturally Significant Use Cases

This project demonstrates four core architectural behaviors that ensure sustainability, resilience, and reliability.

### **Use Case 1: Optimized "Green" Routing**
**Scenario:** The grid is currently running on renewable energy (Low Carbon Intensity).
* **Behavior:** The Orchestrator detects the "Green" status and routes the request to the **XGBoost Service**. This model is computationally heavier but provides maximum accuracy.
* **Significance:** Demonstrates the core logic of "Green Intelligence"—spending energy only when it is environmentally cheap.

![Use Case 1](https://github.com/Apurba1001/AI-Forecasting-for-Renewable-Energy-/blob/Andreas/diagrams/Use_Case_1_Base_Logic.jpg)


### **Use Case 2: Eco-Mode Adaptation (High Carbon Grid)**
**Scenario:** The grid is currently relying on coal or gas (High Carbon Intensity).
* **Behavior:** The Orchestrator detects the "Dirty" status and automatically downgrades the request to the **Holt-Winters Service.**
* **Significance:** Shows the system's ability to trade off minor accuracy for significant energy savings

![Use Case 2](https://github.com/Apurba1001/AI-Forecasting-for-Renewable-Energy-/blob/Andreas/diagrams/Use_Case_2_Eco_Mode_adaption.jpg)

### **Use Case 3: Automatic Failover (Resilience)**
**Scenario:** The Orchestrator attempts to use the primary model (XGBoost), but the service is unresponsive
* **Behavior:** The Orchestrator catches the connection error and immediately fails over to the **Holt-Winters Service.**
* **Significance:** Ensures **High Availability**. The user still receives a valid forecast without ever seeing an error screen.

![Use Case 3](https://github.com/Apurba1001/AI-Forecasting-for-Renewable-Energy-/blob/Andreas/diagrams/Use_Case_3_automatic_fallback.jpg)

### **Use Case 4: Emergency Static Mode (Total System Failure)**
**Scenario:** Both the primary (XGBoost) and secondary (Holt-Winters) services are offline.
* **Behavior:** The API Gateway catches the critical failure from the Orchestrator and activates the **Emergency Static Fallback** generator.
* **Significance:** Ensures **High Availability**. The user still receives a valid forecast without ever seeing an error screen.

![Use Case 4](https://github.com/Apurba1001/AI-Forecasting-for-Renewable-Energy-/blob/Andreas/diagrams/Use_Case_3_emergency_static_mode.jpg)


---
