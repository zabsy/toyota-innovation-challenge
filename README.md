# Toyota Innovation Challenge

> Submission for the **S26 Toyota Innovation Challenge** — an intelligent manufacturing assistant that combines robotics, computer vision, and voice interaction to improve efficiency, safety, and automation in industrial environments.

## Award Recognition

This project was recognized with the **Safety Award** at the S26 Toyota Innovation Challenge for its focus on improving workplace safety through intelligent monitoring, voice-assisted interaction, and automated manufacturing support systems.

## Overview

The Toyota Innovation Challenge project is a multi-disciplinary system designed to support manufacturing operations through automated defect detection, robotic assistance, object localization, and voice-driven interaction.

The platform integrates computer vision, robotic control systems, and an interactive user interface into a unified workflow that assists operators with inspection, navigation, and task execution on the manufacturing floor.

---

## Features

### Vision-Based Defect Detection
- Automated inspection of parts and components using computer vision.
- Detects manufacturing defects from camera feeds and captured images.
- Supports real-time analysis and operator feedback.

### Voice Assistant (Jarvis)
- Voice-activated assistant capable of processing spoken commands.
- Wake-word detection and audio processing.
- Provides hands-free interaction for manufacturing personnel.

### Robot Arm Control
- Interfaces with robotic hardware for automated task execution.
- Dedicated control modules for movement and manipulation.
- Designed for manufacturing and material-handling workflows.

### Bin Localization
- Computer vision system for locating bins, containers, or storage locations.
- Helps guide robotic systems and operators to target objects.
- Enables spatial awareness within the workspace.

### Real-Time User Interface
- Central dashboard connecting vision, robotics, and assistant modules.
- Provides monitoring and control capabilities.
- Simplifies interaction between users and system components.

### Safety Integration
- Includes specialized modules related to workplace safety and monitoring.
- Designed to support safe operation in industrial environments.
- Contributed to the team's Safety Award recognition at the Toyota Innovation Challenge.

---

## System Architecture

```text
                    ┌───────────────────┐
                    │   User Interface  │
                    └─────────┬─────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ Jarvis Voice │ │ Vision System│ │ Robot Control│
      │ Assistant    │ │ & Inspection │ │ Modules      │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │                │                │
             ▼                ▼                ▼
      Audio Processing   Defect Detection   Arm Movement
                          Bin Localization   Hardware I/O
```

---

## Repository Structure

```text
.
├── arm_control/               # Robotic arm control logic
├── ui/                        # Frontend/UI components
├── hardhat_module/            # Safety-related functionality
├── DB/                        # Database and system state files
├── TMMC-CAD-files-ayush/      # CAD models and design assets
├── jarvisAssistant.py         # Voice assistant and audio processing
├── binLocator.py              # Bin localization utility
├── requirements.txt           # Python dependencies
└── README.md
```

---

## Technology Stack

### Languages
- Python
- C++
- HTML

### Technologies
- Computer Vision
- Robotics Control
- Speech Recognition
- Audio Processing
- Hardware Integration
- Database Management

### Hardware
- Raspberry Pi (or compatible embedded systems)
- Camera modules
- Robotic arm hardware
- Industrial sensors

---

## Installation

### Prerequisites

Before getting started, ensure you have:

- Python 3.9+
- Git
- Camera hardware (for vision modules)
- Robotic hardware (optional)
- Microphone (for voice assistant features)

### Clone the Repository

```bash
git clone https://github.com/zabsy/toyota-innovation-challenge.git
cd toyota-innovation-challenge
```

### Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows**

```bash
venv\Scripts\activate
```

**macOS/Linux**

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

### Launch the Voice Assistant

```bash
python jarvisAssistant.py
```

Starts the Jarvis voice assistant and enables wake-word detection and audio interaction.

### Run Bin Localization

```bash
python binLocator.py
```

Launches the computer vision module responsible for locating bins and storage containers.

### Start the User Interface

```bash
cd ui
```

Launch the frontend application according to the framework used within the project.

---

## Example Workflow

1. Operator issues a voice command to Jarvis.
2. Jarvis processes the request.
3. The vision system identifies the target bin or component.
4. Defect detection verifies product quality.
5. Robotic arm executes the requested task.
6. Results are displayed through the user interface.

---

## Development

Recommended formatting and linting tools:

```bash
black .
```

```bash
flake8 .
```

---

## Future Improvements

- Enhanced AI-powered defect classification
- Improved robotic path planning
- Cloud-based analytics and reporting
- Multi-camera support
- Advanced safety monitoring
- Digital twin integration
- Predictive maintenance capabilities

---

## Contributors

Developed as part of the **S26 Toyota Innovation Challenge**.

Contributions were made by team members across software engineering, robotics, computer vision, hardware integration, and user experience design.

---

## Results

**Safety Award Winner — S26 Toyota Innovation Challenge**

The project was recognized for its emphasis on workplace safety, intelligent monitoring systems, and operator assistance technologies that help create safer manufacturing environments.

---

## License

This project was developed for the Toyota Innovation Challenge.

Please consult the repository owners before reusing or distributing project assets.

---

## Acknowledgments

Special thanks to:
- Toyota Motor Manufacturing teams
- Challenge mentors and organizers
- Open-source communities supporting robotics, computer vision, and speech technologies
