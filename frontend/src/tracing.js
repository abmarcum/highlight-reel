import { WebTracerProvider, BatchSpanProcessor } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { trace } from '@opentelemetry/api';

const provider = new WebTracerProvider({
  resource: {
    attributes: {
      'service.name': 'highlight-reel-frontend'
    }
  }
});

// Using standard OTLP HTTP exporter. In a real GCP environment, this might point to 
// an OpenTelemetry Collector running in the same project, or be handled by the GCP Web Exporter.
const exporter = new OTLPTraceExporter({
  url: '/v1/traces' // Assuming a proxy routes this to the OTel collector
});

provider.addSpanProcessor(new BatchSpanProcessor(exporter));
provider.register({
  contextManager: new ZoneContextManager()
});

registerInstrumentations({
  instrumentations: [
    new DocumentLoadInstrumentation(),
    new FetchInstrumentation(),
  ]
});

// Export a basic logging utility that sends structured logs
export const logEvent = (level, message, attributes = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    ...attributes
  };
  
  // Forward log to the same OTLP collector (assuming it has a logs endpoint)
  // or a custom logs ingestion endpoint.
  fetch('/v1/logs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify([logEntry]) // Simplified for illustration
  }).catch(err => console.error('Failed to send log', err));
  
  // Also log to console for local debugging
  console[level === 'error' ? 'error' : 'log'](JSON.stringify(logEntry));
};

export const getTracer = () => trace.getTracer('highlight-reel-frontend');
