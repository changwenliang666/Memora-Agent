# dev-infra Specification

## Purpose

让开发者在本机用一条 Compose 命令拉起 MySQL、Redis、RabbitMQ 和 Qdrant，供仍跑在宿主机上的应用连接，而不把应用进程放进容器。

## Requirements

### Requirement: Compose starts the three middleware services only

The repository SHALL provide a Compose definition that starts MySQL, Redis, RabbitMQ, and Qdrant. That definition MUST NOT start the FastAPI application. After the stack is up, a process on the host MUST be able to reach each service on a published localhost port.

#### Scenario: Host can reach published ports

- **WHEN** a developer starts the Compose stack
- **THEN** MySQL accepts connections on localhost port 3306, Redis on 6379, RabbitMQ AMQP on 5672, and Qdrant HTTP on 6333

#### Scenario: Application is not a Compose service

- **WHEN** a developer starts the Compose stack
- **THEN** no application / FastAPI container is created

### Requirement: Middleware credentials come from the environment file

Compose SHALL interpolate MySQL and RabbitMQ usernames, passwords, and database name from the same environment names the application snapshot reads. The Compose file MUST NOT embed production secrets. Redis and Qdrant MAY start without a password or API key in this development stack.

#### Scenario: Application and Compose share names

- **WHEN** `.env` sets MySQL user, password, and database name
- **THEN** the MySQL container is created with those values, and the application snapshot reads the same names for its connection fields

### Requirement: Middleware data survives a stack restart

Each of MySQL, Redis, RabbitMQ, and Qdrant MUST persist data on a named Docker volume. Restarting the stack MUST NOT wipe those volumes. The volumes MUST NOT be bind-mounted into the project source tree.

#### Scenario: Restart keeps MySQL data

- **WHEN** a developer writes data to MySQL and then restarts the Compose stack
- **THEN** that data is still present

#### Scenario: Restart keeps Qdrant data

- **WHEN** a developer writes vectors to Qdrant and then restarts the Compose stack
- **THEN** those vectors are still present

### Requirement: Services report readiness

Each middleware service MUST define a health check. The published ports are intended for use only after the corresponding service is healthy.

#### Scenario: Unhealthy service is visible

- **WHEN** a middleware process is not yet accepting connections
- **THEN** Compose reports that service as not healthy
