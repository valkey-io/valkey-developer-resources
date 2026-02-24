// Node.js/TypeScript GLIDE Configuration Template
// Optimized for production web applications

import { GlideClient, GlideClusterClient, ReadFrom } from '@valkey/valkey-glide';

// Standalone Client Configuration
export const standaloneConfig = {
  addresses: [{ host: 'localhost', port: 6379 }],
  
  // Request timeout (500ms recommended for web apps)
  requestTimeout: 500,
  
  // Connection retry strategy
  connectionBackoff: {
    numberOfRetries: 10,
    factor: 500,        // Base delay in ms
    exponentBase: 2,    // Exponential backoff
  },
  
  // Client name for debugging
  clientName: 'my-app-client',
  
  // Lazy connect for serverless/Lambda
  lazyConnect: false,  // Set to true for Lambda
  
  // High-throughput configuration
  inflightRequestsLimit: 2000,  // Default: 1000
};

// Cluster Client Configuration
export const clusterConfig = {
  addresses: [{ host: 'cluster.endpoint.cache.amazonaws.com', port: 6379 }],
  
  // Request timeout
  requestTimeout: 500,
  
  // AZ Affinity for cost optimization (read-heavy workloads)
  readFrom: 'AZAffinity' as ReadFrom,
  clientAz: 'us-east-1a',  // Your application's AZ
  
  // Connection retry strategy
  connectionBackoff: {
    numberOfRetries: 10,
    factor: 500,
    exponentBase: 2,
  },
  
  // Client name
  clientName: 'my-app-cluster-client',
  
  // High-throughput configuration
  inflightRequestsLimit: 2000,
};

// Create clients (do this once at application startup)
export async function createClients() {
  const standalone = await GlideClient.createClient(standaloneConfig);
  const cluster = await GlideClusterClient.createClient(clusterConfig);
  
  return { standalone, cluster };
}

// Graceful shutdown
export async function closeClients(standalone: GlideClient, cluster: GlideClusterClient) {
  await standalone.close();
  await cluster.close();
}
