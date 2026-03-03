"""
Firebase Admin SDK configuration and initialization.
Critical: Secure service account credentials should be loaded from environment variables or secure storage.
"""
import os
import logging
from typing import Optional
from dataclasses import dataclass

import firebase_admin
from firebase_admin import credentials, firestore, db

logger = logging.getLogger(__name__)


@dataclass
class FirebaseConfig:
    """Firebase configuration data class with validation."""
    project_id: str
    database_url: str
    service_account_path: Optional[str] = None
    service_account_dict: Optional[dict] = None
    
    def validate(self) -> bool:
        """Validate Firebase configuration."""
        if not self.project_id:
            raise ValueError("Firebase project_id is required")
        if not self.database_url:
            raise ValueError("Firebase database_url is required")
        if not (self.service_account_path or self.service_account_dict):
            raise ValueError("Either service_account_path or service_account_dict must be provided")
        return True


class FirebaseClient:
    """Singleton Firebase client manager with error handling and reconnection logic."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.firestore_client = None
            self.realtime_db = None
            self._initialized = True
    
    def initialize(self, config: FirebaseConfig) -> None:
        """
        Initialize Firebase Admin SDK with robust error handling.
        
        Args:
            config: Validated FirebaseConfig object
            
        Raises:
            ValueError: If configuration is invalid
            firebase_admin.exceptions.FirebaseError: If Firebase initialization fails
        """
        try:
            config.validate()
            
            # Check if Firebase app is already initialized
            if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
                logger.warning("Firebase app already initialized, using existing instance")
                app = firebase_admin.get_app()
            else:
                # Initialize with service account
                if config.service_account_path:
                    if not os.path.exists(config.service_account_path):
                        raise FileNotFoundError(
                            f"Service account file not found: {config.service_account_path}"
                        )
                    cred = credentials.Certificate(config.service_account_path)
                else:
                    cred = credentials.Certificate(config.service_account_dict)
                
                app = firebase_admin.initialize_app(
                    credential=cred,
                    options={
                        'projectId': config.project_id,
                        'databaseURL': config.database_url
                    }
                )
                logger.info(f"Firebase initialized for project: {config.project_id}")
            
            # Initialize clients
            self.firestore_client = firestore.client(app)
            self.realtime_db = db.reference('/', app=app)
            
            # Test connection
            self._test_connection()
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    def _test_connection(self) -> None:
        """Test Firebase connection with timeout and retry logic."""
        import time
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Simple Firestore operation to test connection
                test_ref = self.firestore_client.collection('connection_tests').document('test')
                test_ref.set({'timestamp': firestore.SERVER_TIMESTAMP})
                test_ref.delete()
                logger.info("Firebase connection test successful")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Firebase connection test failed (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Firebase connection test failed after {max_retries} attempts: {e}")
                    raise
    
    def get_firestore(self) -> firestore.Client:
        """Get Firestore client with null check."""
        if self.firestore_client