// Go GLIDE Configuration Template
// Optimized for production web applications

package config

import (
	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
)

// StandaloneConfig returns a production-ready standalone client configuration.
func StandaloneConfig() *config.ClientConfiguration {
	return config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).

		// Request timeout (500ms recommended for web apps)
		WithRequestTimeout(500). // milliseconds

		// Connection retry strategy
		WithReconnectStrategy(config.NewBackoffStrategy(
			10,  // numberOfRetries
			500, // factor (base delay in ms)
			2,   // exponentBase
		)).

		// Client name for debugging
		WithClientName("my-app-client")
}

// Note: inflightRequestsLimit is currently not exposed in the Go config builder.
// It is managed at the Rust core level (default: 1000). Other languages
// that expose this setting, see the respective config templates.

// ClusterConfig returns a production-ready cluster client configuration.
func ClusterConfig() *config.ClusterClientConfiguration {
	return config.NewClusterClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "cluster.endpoint.cache.amazonaws.com", Port: 6379}).

		// Request timeout
		WithRequestTimeout(500).

		// AZ Affinity for cost optimization (read-heavy workloads)
		WithReadFrom(config.AzAffinity).
		WithClientAZ("us-east-1a"). // Your application's AZ

		// Connection retry strategy
		WithReconnectStrategy(config.NewBackoffStrategy(
			10,  // numberOfRetries
			500, // factor (base delay in ms)
			2,   // exponentBase
		)).

		// Client name
		WithClientName("my-app-cluster-client")
}

// Clients holds both standalone and cluster clients.
type Clients struct {
	Standalone *glide.Client
	Cluster    *glide.ClusterClient
}

// CreateClients creates both clients (do this once at application startup).
func CreateClients() (*Clients, error) {
	standalone, err := glide.NewClient(StandaloneConfig())
	if err != nil {
		return nil, err
	}

	cluster, err := glide.NewClusterClient(ClusterConfig())
	if err != nil {
		standalone.Close()
		return nil, err
	}

	return &Clients{
		Standalone: standalone,
		Cluster:    cluster,
	}, nil
}

// Close gracefully shuts down both clients.
func (c *Clients) Close() {
	if c.Standalone != nil {
		c.Standalone.Close()
	}
	if c.Cluster != nil {
		c.Cluster.Close()
	}
}
