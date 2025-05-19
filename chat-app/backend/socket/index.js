const activeUsers = new Set();

module.exports = (io) => {
  io.on('connection', (socket) => {
    console.log('🔌 New client connected:', socket.id);

    socket.on('new_user', (userId) => {
      activeUsers.add(userId);
      io.emit('active_users', Array.from(activeUsers));
    });

    socket.on('join_room', (room) => {
      socket.join(room);
      console.log(`👥 User joined room: ${room}`);
    });

    socket.on('send_message', (data) => {
      io.to(data.room).emit('receive_message', data);
    });

    socket.on('disconnect', () => {
      console.log('❌ Client disconnected');
      activeUsers.forEach(user => {
        if (user.socketId === socket.id) {
          activeUsers.delete(user.userId);
          io.emit('active_users', Array.from(activeUsers));
        }
      });
    });
  });
};
