# [Agentic] (Base) Echo

This is a simple AgentEx agent that just says hello and acknowledges the user's message to show which ACP methods need to be implemented for the base agentic ACP type.

## Building the Agent

To build the agent Docker image locally:

1. First, set up CodeArtifact authentication:
```bash
../../../setup-build-codeartifact.sh
```

2. Build the agent image:
```bash
agentex agents build --manifest manifest.yaml --secret 'id=codeartifact-pip-conf,src=.codeartifact-pip-conf'
```

## Official Documentation

[000 Hello Base Agentic](https://agentex.scale.com/docs/tutorials/agentic/000_hello_base_agentic)
