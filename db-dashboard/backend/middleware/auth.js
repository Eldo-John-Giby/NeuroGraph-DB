if (!process.env.DATABASE_URL && !process.env.JWT_SECRET) {
  require('dotenv').config({ path: require('path').resolve(__dirname, '../.env'), quiet: true });
}

const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'neurograph-db-secret-key-2026';

// Middleware to authenticate JWT token
// Supports optional auth on read-only GET endpoints (e.g. CLI curl or public preview)
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1]; // Bearer <token>

  if (!token) {
    if (['GET', 'HEAD'].includes(req.method) && !req.path.includes('audit-logs')) {
      req.user = { id: null, username: 'guest', role: 'RESEARCHER' };
      return next();
    }
    return res.status(401).json({ error: 'Access denied: No token provided' });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      if (['GET', 'HEAD'].includes(req.method) && !req.path.includes('audit-logs')) {
        req.user = { id: null, username: 'guest', role: 'RESEARCHER' };
        return next();
      }
      return res.status(403).json({ error: 'Invalid or expired token' });
    }
    req.user = user;
    next();
  });
}

// Middleware to authorize specific roles (RBAC)
function requireRole(...allowedRoles) {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        error: `Forbidden: Requires one of roles: [${allowedRoles.join(', ')}]. Current role: ${req.user.role}`
      });
    }
    next();
  };
}

module.exports = {
  JWT_SECRET,
  authenticateToken,
  requireRole,
};
