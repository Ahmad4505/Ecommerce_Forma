export function authDestination(user, requested) {
 if (!user || !['customer','vendor','admin'].includes(user.role)) return '/login';
 if (user.role === 'vendor' && user.vendorStatus !== 'APPROVED') return '/vendor-pending';
 const fallback = user.role === 'customer' ? '/account' : `/${user.role}`;
 if (typeof requested !== 'string' || !requested.startsWith('/') || requested.startsWith('//') || /[\\\u0000-\u001f]/.test(requested)) return fallback;
 const path = requested.split(/[?#]/)[0];
 const required = /^\/(account(?:\/|$)|checkout(?:\/|$))/.test(path) ? 'customer'
  : /^\/admin(?:\/|$)/.test(path) ? 'admin'
  : /^\/vendor(?:$|\/(products|inventory|orders|analytics|store|reviews)(?:\/|$))/.test(path) ? 'vendor' : null;
 return required && required !== user.role ? fallback : requested;
}
