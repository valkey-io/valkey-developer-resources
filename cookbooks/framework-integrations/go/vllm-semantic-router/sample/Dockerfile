FROM golang:1.24

WORKDIR /app

COPY go.mod .
COPY main.go router_client.go .

RUN go build -o router-client .

ENTRYPOINT ["/app/router-client"]
