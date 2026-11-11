---
subtitle: What your code does, and what the provider does
audience: Developers and technical founders building their first AI feature
objective: Show where application logic ends and the external model API begins
key_message: Your backend owns the prompt, the key and the response handling; the provider only runs the model.
duration_s: 60
tone: clear, confident, a little dry
---

# How an AI app talks to an LLM API

When your app shows an AI answer, it looks like magic. It's really a well-behaved HTTP request with good manners.

## Two sides of the line

On the left is yours: the app your users touch and the backend you deploy. On the right is the model provider. Between them, one network call.

```diagram
zones:
  - { id: yours, label: "Your app + backend", kind: internal }
  - { id: provider, label: "Model provider", kind: external }
nodes:
  - { id: app, label: "App UI", zone: yours }
  - { id: backend, label: "Your backend", zone: yours }
  - { id: api, label: "LLM API", zone: provider }
edges:
  - { from: app, to: backend, label: "user question", style: request }
  - { from: backend, to: api, label: "HTTPS request", style: request }
```

## Building the request

Your backend assembles the request: a system prompt, the conversation so far, and settings like model and token limit. The API key is attached here, on the server. It never reaches the browser.

- System prompt sets the rules
- Messages carry the conversation
- Parameters pick model and limits
- API key stays server-side

## Over the wire

The request travels over HTTPS. The provider checks your key, applies rate limits, and runs the model.

```diagram
zones:
  - { id: yours, label: "Your backend", kind: internal }
  - { id: provider, label: "Model provider", kind: external }
nodes:
  - { id: backend, label: "Backend", zone: yours }
  - { id: gateway, label: "API gateway", zone: provider }
  - { id: model, label: "Model", zone: provider }
edges:
  - { from: backend, to: gateway, label: "auth + rate limit", style: request }
  - { from: gateway, to: model, label: "inference", style: request }
```

## The response comes back

Tokens stream back as they are generated. Your backend parses them, applies your own checks, and forwards the result to the app, which renders the answer.

```diagram
zones:
  - { id: yours, label: "Your app + backend", kind: internal }
  - { id: provider, label: "Model provider", kind: external }
nodes:
  - { id: app, label: "App UI", zone: yours }
  - { id: backend, label: "Your backend", zone: yours }
  - { id: api, label: "LLM API", zone: provider }
edges:
  - { from: api, to: backend, label: "streamed tokens", style: stream }
  - { from: backend, to: app, label: "rendered answer", style: response }
```

## Recap

You own the prompt, the key, and the answer's journey. The provider owns the model. Keep that line clear; the rest is plumbing.

- You own: prompt, key, response handling
- Provider owns: running the model
- The line between them: one HTTPS call
