"""HTTP client with connection pooling for IHE transactions.

This module provides HTTP client functionality with configurable connection pooling
to support efficient batch processing of IHE transactions (PIX Add, ITI-41).

Supports NFR3: 10+ concurrent connections for batch processing.
"""

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Default connection pool settings
DEFAULT_MAX_CONNECTIONS = 10
DEFAULT_POOL_BLOCK = True
DEFAULT_RETRY_COUNT = 3
DEFAULT_BACKOFF_FACTOR = 0.3
DEFAULT_TIMEOUT = 30


@dataclass
class ConnectionPoolConfig:
    """Configuration for HTTP connection pooling.
    
    Attributes:
        max_connections: Maximum number of connections in the pool.
            Must be >= 1. NFR3 requires support for 10+ connections.
        pool_block: Whether to block when pool is exhausted.
            If True, requests wait for a connection. If False, raises error.
        retry_count: Number of retries for failed requests.
        backoff_factor: Factor for exponential backoff between retries.
        timeout: Default timeout for requests in seconds.
        
    Example:
        >>> config = ConnectionPoolConfig(max_connections=20, pool_block=True)
        >>> pool = ConnectionPool(config)
        >>> session = pool.get_session()
    """
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    pool_block: bool = DEFAULT_POOL_BLOCK
    retry_count: int = DEFAULT_RETRY_COUNT
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    timeout: int = DEFAULT_TIMEOUT
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_connections < 1:
            raise ValueError(
                f"max_connections must be >= 1, got {self.max_connections}"
            )
        if self.retry_count < 0:
            raise ValueError(
                f"retry_count must be >= 0, got {self.retry_count}"
            )
        if self.backoff_factor < 0:
            raise ValueError(
                f"backoff_factor must be >= 0, got {self.backoff_factor}"
            )
        if self.timeout < 1:
            raise ValueError(
                f"timeout must be >= 1, got {self.timeout}"
            )


class ConnectionPool:
    """Manages HTTP connection pooling for efficient batch processing.
    
    Provides reusable HTTP sessions with configurable connection pools,
    retry logic, and timeout settings. Thread-safe for concurrent use.
    
    Attributes:
        config: Connection pool configuration.
        
    Example:
        >>> pool = ConnectionPool(ConnectionPoolConfig(max_connections=15))
        >>> session = pool.get_session()
        >>> response = session.post(url, data=payload)
        >>> pool.close()
    """
    
    def __init__(self, config: Optional[ConnectionPoolConfig] = None) -> None:
        """Initialize connection pool with configuration.
        
        Args:
            config: Pool configuration. Uses defaults if not provided.
        """
        self.config = config or ConnectionPoolConfig()
        self._session: Optional[requests.Session] = None
        self._lock = Lock()
        logger.debug(
            "ConnectionPool initialized with max_connections=%d, pool_block=%s",
            self.config.max_connections,
            self.config.pool_block,
        )
    
    def get_session(self, max_connections: Optional[int] = None) -> requests.Session:
        """Get or create a configured HTTP session with connection pooling.
        
        The session is created lazily on first call and reused for subsequent
        calls. Thread-safe - multiple threads can safely call this method.
        
        Args:
            max_connections: Override max connections for this session.
                Uses config value if not provided.
                
        Returns:
            Configured requests.Session with connection pooling and retry logic.
            
        Example:
            >>> pool = ConnectionPool()
            >>> session = pool.get_session(max_connections=20)
            >>> response = session.post("https://example.com/api", data=data)
        """
        with self._lock:
            if self._session is None:
                self._session = self._create_session(max_connections)
            return self._session
    
    def _create_session(self, max_connections: Optional[int] = None) -> requests.Session:
        """Create a new session with connection pooling configuration.
        
        Args:
            max_connections: Override max connections. Uses config if None.
            
        Returns:
            Configured requests.Session.
        """
        pool_connections = max_connections or self.config.max_connections
        
        # Create retry strategy
        retry_strategy = Retry(
            total=self.config.retry_count,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
        )
        
        # Create adapter with connection pool
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_connections,
            pool_block=self.config.pool_block,
            max_retries=retry_strategy,
        )
        
        # Create session and mount adapter
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        logger.info(
            "Created HTTP session with pool_connections=%d, pool_maxsize=%d, "
            "pool_block=%s, retry_count=%d",
            pool_connections,
            pool_connections,
            self.config.pool_block,
            self.config.retry_count,
        )
        
        return session
    
    def close(self) -> None:
        """Close the session and release resources.
        
        Should be called when the pool is no longer needed to properly
        release connections and resources.
        
        Example:
            >>> pool = ConnectionPool()
            >>> session = pool.get_session()
            >>> # ... use session ...
            >>> pool.close()
        """
        with self._lock:
            if self._session is not None:
                self._session.close()
                self._session = None
                logger.debug("ConnectionPool session closed")
    
    def reset(self) -> None:
        """Reset the connection pool by closing and recreating the session.
        
        Useful when connection state needs to be cleared, such as after
        authentication changes or connection errors.
        
        Example:
            >>> pool = ConnectionPool()
            >>> # ... some operations ...
            >>> pool.reset()  # Clear all connections
            >>> session = pool.get_session()  # New session created
        """
        with self._lock:
            if self._session is not None:
                self._session.close()
                self._session = None
                logger.debug("ConnectionPool reset - session will be recreated on next use")
    
    def __enter__(self) -> "ConnectionPool":
        """Enter context manager.
        
        Returns:
            Self for context manager usage.
            
        Example:
            >>> with ConnectionPool() as pool:
            ...     session = pool.get_session()
            ...     response = session.post(url, data=data)
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, closing the pool.
        
        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        self.close()


# Module-level singleton for simple usage
_default_pool: Optional[ConnectionPool] = None
_default_lock = Lock()


def get_default_pool(config: Optional[ConnectionPoolConfig] = None) -> ConnectionPool:
    """Get or create the default connection pool singleton.
    
    Provides a convenient way to share a single connection pool across
    the application. Thread-safe.
    
    Args:
        config: Pool configuration for initial creation. Ignored if pool exists.
        
    Returns:
        The default ConnectionPool instance.
        
    Example:
        >>> pool = get_default_pool()
        >>> session = pool.get_session()
        >>> response = session.post(url, data=data)
    """
    global _default_pool
    with _default_lock:
        if _default_pool is None:
            _default_pool = ConnectionPool(config)
            logger.debug("Default connection pool created")
        return _default_pool


def reset_default_pool() -> None:
    """Reset the default connection pool.
    
    Closes and removes the default pool. Next call to get_default_pool()
    will create a new pool.
    
    Example:
        >>> reset_default_pool()
        >>> pool = get_default_pool(ConnectionPoolConfig(max_connections=30))
    """
    global _default_pool
    with _default_lock:
        if _default_pool is not None:
            _default_pool.close()
            _default_pool = None
            logger.debug("Default connection pool reset")


def create_session_with_pool(
    max_connections: int = DEFAULT_MAX_CONNECTIONS,
    pool_block: bool = DEFAULT_POOL_BLOCK,
    retry_count: int = DEFAULT_RETRY_COUNT,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> requests.Session:
    """Create a standalone HTTP session with connection pooling.
    
    Convenience function for creating a one-off session without
    managing a ConnectionPool instance.
    
    Args:
        max_connections: Maximum connections in pool (default: 10).
        pool_block: Block when pool exhausted (default: True).
        retry_count: Number of retries (default: 3).
        backoff_factor: Backoff factor for retries (default: 0.3).
        
    Returns:
        Configured requests.Session. Caller is responsible for closing.
        
    Example:
        >>> session = create_session_with_pool(max_connections=15)
        >>> try:
        ...     response = session.post(url, data=data)
        ... finally:
        ...     session.close()
    """
    config = ConnectionPoolConfig(
        max_connections=max_connections,
        pool_block=pool_block,
        retry_count=retry_count,
        backoff_factor=backoff_factor,
    )
    pool = ConnectionPool(config)
    return pool.get_session()
