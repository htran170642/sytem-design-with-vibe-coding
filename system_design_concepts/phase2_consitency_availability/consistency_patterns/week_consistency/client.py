# client.py - FIXED with proper bounds
import socket
import json
import threading
import time
import random
import os

class GameClient:
    def __init__(self, player_id, server_host='localhost', server_port=9000):
        self.player_id = player_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', 0))
        self.server_addr = (server_host, server_port)
        
        # My position (start in valid range)
        self.x = random.randint(20, 80)
        self.y = random.randint(20, 80)
        
        # Other players
        self.other_players = {}
        self.lock = threading.Lock()
        
        # Stats for weak consistency demo
        self.packets_sent = 0
        self.updates_received = 0
    
    def send_position(self):
        """Send position updates to server"""
        while True:
            # Create update message
            message = json.dumps({
                'player_id': self.player_id,
                'x': self.x,
                'y': self.y
            }).encode()
            
            # Send via UDP (fire and forget)
            self.sock.sendto(message, self.server_addr)
            self.packets_sent += 1
            
            # Simulate random movement
            dx = random.randint(-3, 3)
            dy = random.randint(-3, 3)
            
            # Update position with proper bounds checking
            self.x = max(0, min(100, self.x + dx))
            self.y = max(0, min(100, self.y + dy))
            
            time.sleep(0.1)  # 10 updates/sec
    
    def receive_updates(self):
        """Receive other players' positions"""
        while True:
            try:
                data, _ = self.sock.recvfrom(1024)
                state = json.loads(data.decode())
                
                with self.lock:
                    self.other_players = state
                    self.updates_received += 1
                
            except Exception as e:
                # Packet lost - this is expected with UDP
                pass
    
    def display_loop(self):
        """Display game state"""
        while True:
            with self.lock:
                # Clear screen
                os.system('clear' if os.name != 'nt' else 'cls')
                
                print("=" * 60)
                print(f"🎮 WEAK CONSISTENCY GAME - Player: {self.player_id}")
                print("=" * 60)
                
                # My position
                print(f"\n📍 My position: ({self.x}, {self.y})")
                
                # Other players
                print(f"\n👥 Other players ({len(self.other_players)}):")
                if self.other_players:
                    for pid, pos in sorted(self.other_players.items()):
                        dx = pos['x'] - self.x
                        dy = pos['y'] - self.y
                        distance = (dx**2 + dy**2) ** 0.5
                        
                        # Direction indicator
                        direction = ""
                        if abs(dx) > abs(dy):
                            direction = "→" if dx > 0 else "←"
                        else:
                            direction = "↓" if dy > 0 else "↑"
                        
                        print(f"   {direction} {pid:12s}: ({pos['x']:3d}, {pos['y']:3d})  " 
                              f"[{distance:5.1f}m away]")
                else:
                    print("   (Waiting for other players...)")
                
                # Stats
                # print(f"\n📊 Network Stats:")
                # print(f"   Packets sent: {self.packets_sent}")
                # print(f"   Updates received: {self.updates_received}")
                # if self.packets_sent > 0:
                #     ratio = self.updates_received / self.packets_sent
                #     print(f"   Receive/Send ratio: {ratio:.2f}")
                
                # # Explanation
                # print(f"\n💡 Weak Consistency in Action:")
                # print(f"   • Using UDP (no delivery guarantee)")
                # print(f"   • Packets may arrive out of order")
                # print(f"   • Positions may 'jump' if updates are lost")
                # print(f"   • Trade-off: Low latency vs Perfect consistency")
                
                # print("=" * 60)
                # print("Press Ctrl+C to quit")
                # print("=" * 60)
            
            time.sleep(1)
    
    def run(self):
        print(f"🚀 Starting {self.player_id}...")
        
        # Start background threads
        sender = threading.Thread(target=self.send_position, daemon=True)
        receiver = threading.Thread(target=self.receive_updates, daemon=True)
        
        sender.start()
        receiver.start()
        
        # Give threads time to start
        time.sleep(0.5)
        
        # Main display loop
        try:
            self.display_loop()
        except KeyboardInterrupt:
            print(f"\n\n👋 {self.player_id} disconnected")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 client.py <player_name>")
        print("Example: python3 client.py Alice")
        sys.exit(1)
    
    player_id = sys.argv[1]
    client = GameClient(player_id)
    client.run()