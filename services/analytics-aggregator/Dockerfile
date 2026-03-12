FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod .
RUN go mod download
COPY . .
RUN go build -o /out/analytics-aggregator ./cmd/server
RUN go build -o /out/analytics-ingester ./cmd/ingester
RUN go build -o /out/analytics-realtime ./cmd/realtime

FROM alpine:3.20
WORKDIR /app
COPY --from=build /out/analytics-aggregator /usr/local/bin/analytics-aggregator
COPY --from=build /out/analytics-ingester /usr/local/bin/analytics-ingester
COPY --from=build /out/analytics-realtime /usr/local/bin/analytics-realtime
CMD ["analytics-realtime"]
