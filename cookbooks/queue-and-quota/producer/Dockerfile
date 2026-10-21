# Build the job producer with no network access. The Go module dependencies are
# vendored into ./vendor (committed to the repo), so the build never contacts a
# module proxy — it works on a locked-down network or an offline machine, and the
# reader needs no Go toolchain installed locally.
FROM golang:1.26 AS build
WORKDIR /src
COPY go.mod go.sum ./
COPY vendor ./vendor
COPY main.go ./
# -mod=vendor uses the committed vendor tree; GOFLAGS/GOPROXY=off guarantee no
# network is attempted.
ENV GOFLAGS=-mod=vendor GOPROXY=off
RUN CGO_ENABLED=0 go build -o /out/producer .

FROM gcr.io/distroless/static-debian12
COPY --from=build /out/producer /producer
ENTRYPOINT ["/producer"]
