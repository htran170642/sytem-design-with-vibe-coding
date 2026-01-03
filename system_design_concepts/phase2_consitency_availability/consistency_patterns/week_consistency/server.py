# server.py - PROPERLY FIXED
import socket
import json
from datetime import datetime

class WeakConsistencyGameServer:
    def __init__(self, host='0.0.0.0', port=9000):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.players = {}
        print(f"🎮 Game server listening on {host}:{port}")
    
    def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = json.loads(data.decode())
                
                player_id = message['player_id']
                x, y = message['x'], message['y']
                
                # Update this player's position
                self.players[player_id] = {
                    'x': x,
                    'y': y,
                    'last_seen': datetime.now(),
                    'addr': addr
                }
                
                print(f"📍 {player_id} → ({x}, {y})")
                
                # Send updated world state to THIS player only
                # (excluding their own position)
                self.send_state_to_player(player_id)
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def send_state_to_player(self, target_player_id):
        """
        Send world state to ONE player, excluding their own position.
        This is the KEY FIX - we send personalized state to each player.
        """
        # Build state for this specific player (exclude themselves)
        state = {
            pid: {'x': p['x'], 'y': p['y']}
            for pid, p in self.players.items()
            if pid != target_player_id  # ← Don't include the target player
        }
        
        # Send only to this player via player's address
        if target_player_id in self.players:
            try:
                message = json.dumps(state).encode()
                addr = self.players[target_player_id]['addr']
                self.sock.sendto(message, addr)
            except Exception as e:
                # Weak consistency - ignore failures
                pass

if __name__ == '__main__':
    server = WeakConsistencyGameServer()
    server.run()