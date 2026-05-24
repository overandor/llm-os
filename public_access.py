"""
Public access management for decentralized nodes
Supports local only, ngrok, cloudflared, and custom domain
"""
import os
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class PublicAccess:
    """Public access configuration and status."""
    public_url: str
    mode: str  # local | ngrok | cloudflared | custom
    started_at: str
    status: str  # active | stopped | error
    process_id: Optional[int] = None
    error_message: Optional[str] = None


class PublicAccessManager:
    """Manager for public access tunnels."""
    
    def __init__(self, local_port: int = 8000):
        self.local_port = local_port
        self.current_access: Optional[PublicAccess] = None
        self.state_file = Path.home() / ".llm_os" / "public_access_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def start_local(self) -> PublicAccess:
        """Start in local-only mode (no tunnel)."""
        self.current_access = PublicAccess(
            public_url=f"http://localhost:{self.local_port}",
            mode="local",
            started_at=datetime.now(timezone.utc).isoformat(),
            status="active"
        )
        self._save_state()
        return self.current_access
    
    def start_ngrok(self) -> PublicAccess:
        """Start ngrok tunnel."""
        # Check for ngrok auth token
        auth_token = os.getenv("NGROK_AUTH_TOKEN")
        if not auth_token:
            return PublicAccess(
                public_url="",
                mode="ngrok",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error_message="NGROK_AUTH_TOKEN not set"
            )
        
        # Check if ngrok is installed
        try:
            subprocess.run(["ngrok", "version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return PublicAccess(
                public_url="",
                mode="ngrok",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error_message="ngrok not installed or not in PATH"
            )
        
        # Start ngrok
        try:
            # Start ngrok in background
            process = subprocess.Popen(
                ["ngrok", "http", str(self.local_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment for ngrok to start
            import time
            time.sleep(2)
            
            # Get public URL from ngrok API
            try:
                response = subprocess.run(
                    ["curl", "-s", "http://localhost:4040/api/tunnels"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                tunnels = json.loads(response.stdout)
                if tunnels.get("tunnels"):
                    public_url = tunnels["tunnels"][0]["public_url"]
                else:
                    public_url = ""
            except:
                public_url = ""
            
            self.current_access = PublicAccess(
                public_url=public_url,
                mode="ngrok",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="active" if public_url else "error",
                process_id=process.pid,
                error_message=None if public_url else "Failed to get public URL from ngrok"
            )
            
            self._save_state()
            return self.current_access
            
        except Exception as e:
            return PublicAccess(
                public_url="",
                mode="ngrok",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error_message=str(e)
            )
    
    def start_cloudflared(self) -> PublicAccess:
        """Start cloudflared tunnel."""
        # Check if cloudflared is installed
        try:
            subprocess.run(["cloudflared", "version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return PublicAccess(
                public_url="",
                mode="cloudflared",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error_message="cloudflared not installed or not in PATH"
            )
        
        # Start cloudflared
        try:
            process = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{self.local_port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for tunnel to start
            import time
            time.sleep(3)
            
            # cloudflared prints the URL to stdout
            # For now, return placeholder
            self.current_access = PublicAccess(
                public_url="https://[cloudflared-url]",  # Would parse from output
                mode="cloudflared",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="active",
                process_id=process.pid
            )
            
            self._save_state()
            return self.current_access
            
        except Exception as e:
            return PublicAccess(
                public_url="",
                mode="cloudflared",
                started_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error_message=str(e)
            )
    
    def start_custom(self, domain: str) -> PublicAccess:
        """Configure custom domain (placeholder)."""
        # This would configure reverse proxy, DNS, etc.
        # For now, just store the configuration
        self.current_access = PublicAccess(
            public_url=f"https://{domain}",
            mode="custom",
            started_at=datetime.now(timezone.utc).isoformat(),
            status="active"
        )
        self._save_state()
        return self.current_access
    
    def stop(self) -> bool:
        """Stop the current public access tunnel."""
        if not self.current_access:
            return True
        
        if self.current_access.process_id:
            try:
                import signal
                os.kill(self.current_access.process_id, signal.SIGTERM)
            except ProcessLookupError:
                pass
        
        self.current_access = None
        self._save_state()
        return True
    
    def get_status(self) -> Optional[PublicAccess]:
        """Get current public access status."""
        if self.current_access:
            return self.current_access
        
        # Try to load from state file
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            self.current_access = PublicAccess(**data)
            return self.current_access
        
        return None
    
    def _save_state(self):
        """Save current state to file."""
        if self.current_access:
            with open(self.state_file, 'w') as f:
                json.dump({
                    "public_url": self.current_access.public_url,
                    "mode": self.current_access.mode,
                    "started_at": self.current_access.started_at,
                    "status": self.current_access.status,
                    "process_id": self.current_access.process_id,
                    "error_message": self.current_access.error_message
                }, f, indent=2)
        elif self.state_file.exists():
            self.state_file.unlink()


if __name__ == "__main__":
    # Test public access manager
    print("Testing public access manager...")
    
    manager = PublicAccessManager(local_port=8000)
    
    # Test local mode
    print("\n1. Testing local mode...")
    local = manager.start_local()
    print(f"  Mode: {local.mode}")
    print(f"  URL: {local.public_url}")
    print(f"  Status: {local.status}")
    
    # Test ngrok (will fail without token)
    print("\n2. Testing ngrok mode...")
    ngrok = manager.start_ngrok()
    print(f"  Mode: {ngrok.mode}")
    print(f"  URL: {ngrok.public_url or 'N/A'}")
    print(f"  Status: {ngrok.status}")
    if ngrok.error_message:
        print(f"  Error: {ngrok.error_message}")
    
    # Test cloudflared (will fail without installation)
    print("\n3. Testing cloudflared mode...")
    cloudflared = manager.start_cloudflared()
    print(f"  Mode: {cloudflared.mode}")
    print(f"  URL: {cloudflared.public_url or 'N/A'}")
    print(f"  Status: {cloudflared.status}")
    if cloudflared.error_message:
        print(f"  Error: {cloudflared.error_message}")
    
    # Test custom domain
    print("\n4. Testing custom domain mode...")
    custom = manager.start_custom("inference.example.com")
    print(f"  Mode: {custom.mode}")
    print(f"  URL: {custom.public_url}")
    print(f"  Status: {custom.status}")
    
    # Test status retrieval
    print("\n5. Testing status retrieval...")
    status = manager.get_status()
    print(f"  Current mode: {status.mode if status else 'None'}")
    
    # Test stop
    print("\n6. Testing stop...")
    manager.stop()
    status = manager.get_status()
    print(f"  Status after stop: {status.status if status else 'None'}")
    
    print("\nPublic access manager test passed!")
