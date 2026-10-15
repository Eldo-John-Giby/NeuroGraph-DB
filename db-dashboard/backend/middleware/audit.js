if (!process.env.DATABASE_URL) {
  require('dotenv').config({ path: require('path').resolve(__dirname, '../.env'), quiet: true });
}

// Express middleware for logging POST/PUT/DELETE requests into the AuditLog table
function createAuditLogger(prisma) {
  return async (req, res, next) => {
    // We only audit state-changing mutations: POST, PUT, PATCH, DELETE
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
      return next();
    }

    // Don't log passwords or sensitive tokens directly in details
    const sanitizedBody = { ...req.body };
    if (sanitizedBody.password) sanitizedBody.password = '[REDACTED]';

    // Intercept finish to capture status and record asynchronously
    res.on('finish', async () => {
      // Only log if request was processed (status < 500) or as appropriate
      try {
        const userId = req.user ? req.user.id : null;
        const action = `${req.method} ${req.baseUrl || ''}${req.path}`;
        const ipAddress = req.ip || req.headers['x-forwarded-for'] || req.socket.remoteAddress;

        await prisma.auditLog.create({
          data: {
            userId: userId,
            action: action,
            method: req.method,
            endpoint: req.originalUrl || req.url,
            ipAddress: typeof ipAddress === 'string' ? ipAddress : null,
            details: JSON.stringify({
              statusCode: res.statusCode,
              body: sanitizedBody,
              query: req.query,
              params: req.params,
            }),
            timestamp: new Date(),
          },
        });
      } catch (err) {
        console.error('Failed to create audit log entry:', err.message);
      }
    });

    next();
  };
}

module.exports = { createAuditLogger };
