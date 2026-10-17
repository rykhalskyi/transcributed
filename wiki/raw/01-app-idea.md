## 1. Objective

Build a self-hosted, Kubernetes-native system to transcribe lecture videos stored on a network NAS. (Lecture languages: English, Russian, German) This is a learning project focused on Kubernetes Jobs, message queues, event-driven autoscaling, and resilient task processing.

## 2. Existing infrastructure

- Kubernetes cluster with two nodes (Talos); a third node is planned.
- Node 1: HP ProDesk Mini, 16 GB RAM, already running other workloads.
- Node 2: Intel Core i5-9500, 6 cores / 6 threads, 19 GB RAM.
- CloudNativePG (CNPG) is already installed and manages PostgreSQL.
- Lecture videos are stored on a network NAS.

## 3. Proposed architecture

- **FastAPI:** control-plane API for submitting lectures, querying task status, and retrieving transcript locations.
- **CloudNativePG / PostgreSQL:** persistent task metadata, lifecycle state, timestamps, errors, and output locations.
- **RabbitMQ:** durable queue of pending transcription tasks.
- **KEDA:** monitors RabbitMQ queue metrics and scales transcription Kubernetes Jobs using `ScaledJob`.
- **Kubernetes Jobs:** execute individual transcription tasks; one lecture per Job.
- **Faster Whisper:** python worker CPU-based speech recognition, initially using the `small` model with INT8 quantization and language explicitly configurable.
- **NAS:** read-only input mount for videos; output mount for transcripts.
- **Local persistent storage or cache volume:** stores downloaded model files to avoid repeatedly downloading them.

## 4. Processing workflow

1. The user submits a lecture through FastAPI.
2. FastAPI creates a unique task record in PostgreSQL and publishes a message containing the task ID and input path to RabbitMQ.
3. KEDA monitors the queue and creates or scales Kubernetes Jobs according to the configured queue target and maximum job count.
4. Each worker claims a task, validates the input, runs Faster Whisper, and writes the transcript to the NAS.
5. The worker updates the task status and output location in PostgreSQL, then acknowledges the RabbitMQ message only after successful processing.
6. Failed tasks follow a defined retry policy. Processing must be idempotent so redelivery does not create conflicting transcripts.
7. Completed Kubernetes Jobs are retained temporarily for debugging and then cleaned up using `ttlSecondsAfterFinished`.

## 5. Initial resource and scheduling policy

- Start with one concurrent transcription Job; increase only after measuring resource use and throughput.
- Initial worker request: 1 CPU and 1 GiB RAM; initial limit: 2 CPUs and 2 GiB RAM. Adjust after testing the selected model on real lectures.
- Use conservative KEDA `maxReplicaCount` / `maxReplicaCount`-equivalent Job limits and resource requests so queue growth does not overwhelm the cluster. Configure the appropriate `ScaledJob` limits for the installed KEDA version.
- Prefer the i5-9500 node for transcription workers initially, using a node label and affinity if necessary. Allow other nodes later if desired.
- Use a Kubernetes Service for RabbitMQ access and persistent storage for broker data. A single broker instance is acceptable for the learning phase, with the understanding that broker downtime temporarily interrupts queue processing.

## 6. Reliability and observability

- Define task states: `queued`, `processing`, `succeeded`, and `failed`.
- Store attempt count, timestamps, error summaries, and transcript paths in PostgreSQL.
- Configure RabbitMQ durable queues and persistent messages; define dead-letter or terminal-failure handling for repeatedly failing tasks.
- Set Kubernetes Job `backoffLimit` and `ttlSecondsAfterFinished` explicitly.
- Monitor queue depth, Job status, Pod restarts, CPU/RAM consumption, transcription duration, and failures.
- Talos has already prometheus and grafana. Use them if possible.
- Keep PostgreSQL and RabbitMQ persistent data separate from ephemeral worker containers. Back up CNPG data and important configuration.

## 7. Suggested implementation milestones

1. Mount the NAS and manually run Faster Whisper against one lecture.
2. Build a worker container that processes one task and exits.
3. Deploy RabbitMQ and verify message publishing, consumption, acknowledgement, and redelivery.
4. Add CNPG task records and FastAPI submission/status endpoints.
5. Deploy Kubernetes Jobs and verify successful completion, retries, and cleanup.
6. Configure KEDA `ScaledJob` to scale from RabbitMQ queue metrics.
7. Test bursts of tasks, worker failures, node unavailability, and resource limits.
8. Add a minimal web interface and tune concurrency based on measured performance.

## 8. Out of scope for the first iteration

- High availability for every service.
- GPU acceleration.
- Multi-cluster scheduling.
- Complex user authentication and multi-user authorization.
- Automatic physical-node provisioning.

The first milestone is a complete, observable end-to-end pipeline for one lecture, followed by queue-driven scaling and controlled failure experiments.
