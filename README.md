# SentinelAI

SentinelAI is an intelligent surveillance system built to reduce the need for humans to continuously watch camera feeds. It converts raw video streams into actionable events, so operators focus on what matters instead of monitoring everything all the time.

## Why SentinelAI

Modern campuses, factories, warehouses, transport hubs, and public spaces use large camera networks. The bottleneck is no longer camera availability, it is human attention.

Common operational challenges:

- Real-time incidents are missed because operators must watch many screens at once.
- Response times are delayed due to manual monitoring fatigue.
- Investigations take too long because footage is reviewed manually after incidents.
- Organizations invest in camera hardware but still depend on human vigilance as the detection layer.

In short, cameras capture data, but data alone is not intelligence.

## What SentinelAI Does

SentinelAI transforms passive camera streams into active monitoring signals.

The system:

1. Ingests camera streams.
2. Processes frames through computer vision.
3. Detects and tracks entities across time.
4. Interprets scene behavior using event logic.
5. Emits structured alerts, logs, and dashboard telemetry.

Instead of reviewing endless footage, operators receive prioritized events and can respond faster.

## Pipeline Overview

SentinelAI uses a modular, production-oriented pipeline:

1. Input Layer
	Captures frames reliably from configured cameras.

2. Preprocessing Layer
	Normalizes frame input for downstream components.

3. Analysis Layer
	Runs detection and tracking to understand scene state over time.

4. Decision Layer
	Applies event rules to convert model output into meaningful incidents while reducing noise.

5. Output Layer
	Produces event logs, alerts, status metrics, and dashboard-friendly APIs.

## Current Architecture In This Repository

- Ingestion: [src/ingestion/camera_ingestion.py](src/ingestion/camera_ingestion.py)
- Detection: [src/detection/person_detector.py](src/detection/person_detector.py)
- Tracking: [src/tracking/tracker.py](src/tracking/tracker.py), [src/tracking/track_manager.py](src/tracking/track_manager.py)
- Event Engine and Rules: [src/events/event_engine.py](src/events/event_engine.py), [src/events](src/events)
- Dashboard/API: [src/dashboard/server.py](src/dashboard/server.py), [src/dashboard/routes.py](src/dashboard/routes.py), [src/dashboard/ws_manager.py](src/dashboard/ws_manager.py)
- Core models/config/heartbeat: [src/core](src/core)
- Runtime modes: [main.py](main.py), [camera_worker.py](camera_worker.py), [supervisor.py](supervisor.py)

## Value Proposition

For security teams:

- Reduced cognitive load in monitoring rooms.
- Faster incident response through event-driven visibility.
- Better use of existing surveillance infrastructure.

For engineering and research:

- A practical example of AI deployed as an operational system, not just a model demo.
- Modular architecture that supports extension and testing.

## Engineering Principles

SentinelAI is being built with a production mindset:

- Modular components with clear responsibilities.
- Config-driven behavior via YAML.
- Structured logging and status reporting.
- Reliability-oriented process management (worker + supervisor model).
- Maintainable repository structure and test coverage foundation.

## Innovation Focus

Many surveillance demos stop at object detection on a sample clip. SentinelAI focuses on end-to-end system design: ingestion, analysis, tracking, decision logic, event output, and operational reliability.

This frames surveillance as a systems engineering problem, not only a machine learning problem.

## Expected Impact

Short term:

- Demonstrates practical reduction of human monitoring load.
- Provides a robust base for iterative capability growth.

Long term:

- Enables deployment patterns suitable for smart cities, industrial safety, and large institutions where continuous observation is needed but human attention is limited.

## Project Stage

SentinelAI is currently in active development. The focus is on stabilizing architecture and workflow first, so future features can be integrated cleanly and reliably.