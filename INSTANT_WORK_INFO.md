# INSTANT WORK INFO - READ ME FIRST (30 March 2026)

ATTENTION!

I made a mistake and pushed a broken version to the public repo.

What happened:
I tried to make the credential file (containing API keys, DB passwords, auth tokens, etc.) readable from both Beasty and Hermes.
Hermes is the permanent Swarm leader node (the "brain" of the system).

During that change I broke the server. 
Now the API is down ("All DB connections failed" + token-count returns 500).

ARGOS still works locally on my GPU (Beasty) and can be used normally, but the Swarm deployment is currently unstable.

I am actively working to fix the credential sharing logic between nodes.
I need a little more time to find exactly what I did wrong.

If anyone sees the exact cause why the server is not starting correctly, please tell me.

Roadmap note:
HERMES v2 (full leader node with proper credential sharing and failover) will be released soon with full code and documentation.

Thank you for understanding.
I will announce here when the repo is clean again.

DarkAngel
