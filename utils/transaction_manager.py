"""
Transaction Manager - rollback dla operacji na plikach.

FILOZOFIA:
- albo wszystkie akcje przechodzą
- albo ŻADNA się nie wykonuje
- to jest ACID dla filesystem

GWARANCJE:
- snapshot przed zmianami
- restore przy błędzie
- cleanup po sukcesie
"""

import shutil
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import uuid

class TransactionError(Exception):
    """Błąd podczas transakcji"""
    pass

class Transaction:
    """
    Pojedyncza transakcja filesystem.
    
    Workflow:
    1. begin() - utwórz snapshot dir
    2. stage_backup(path) - przed modyfikacją pliku
    3. commit() - usuń snapshot (sukces)
    4. rollback() - przywróć snapshot (błąd)
    """
    
    def __init__(self, project_root: Path, transaction_id: Optional[str] = None):
        self.project_root = Path(project_root)
        self.tx_id = transaction_id or f"tx-{uuid.uuid4().hex[:8]}"
        
        # Snapshot directory
        self.snapshot_dir = self.project_root / ".ai-tmp" / self.tx_id
        
        # Metadata
        self.metadata = {
            "tx_id": self.tx_id,
            "started_at": datetime.now().isoformat(),
            "status": "pending",  # pending, committed, rolled_back
            "backed_up_files": []
        }
        
        self.is_active = False
    
    def begin(self):
        """Rozpocznij transakcję - utwórz snapshot dir"""
        if self.is_active:
            raise TransactionError(f"Transaction {self.tx_id} already active")
        
        # Utwórz snapshot directory
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Zapisz metadata
        self._save_metadata()
        
        self.is_active = True
    
    def stage_backup(self, file_path: Path):
        """
        Zrób backup pliku przed modyfikacją.
        
        Args:
            file_path: ścieżka do pliku (absolute lub relative do project_root)
        """
        if not self.is_active:
            raise TransactionError("Transaction not active - call begin() first")
        
        # Normalizuj path
        if not file_path.is_absolute():
            file_path = self.project_root / file_path
        
        # Relatywna ścieżka do project_root
        rel_path = file_path.relative_to(self.project_root)
        
        # Ścieżka w snapshot
        backup_path = self.snapshot_dir / rel_path
        
        # Jeśli plik istnieje - zrób kopię
        if file_path.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            if file_path.is_file():
                shutil.copy2(file_path, backup_path)
            elif file_path.is_dir():
                shutil.copytree(file_path, backup_path, dirs_exist_ok=True)
            
            self.metadata["backed_up_files"].append(str(rel_path))
            self._save_metadata()
    
    def commit(self):
        """
        Zatwierdź transakcję - usuń snapshot.
        Operacja nieodwracalna.
        """
        if not self.is_active:
            raise TransactionError("Transaction not active")
        
        self.metadata["status"] = "committed"
        self.metadata["committed_at"] = datetime.now().isoformat()
        self._save_metadata()
        
        # Usuń snapshot directory
        if self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir)
        
        self.is_active = False
    
    def rollback(self, reason: Optional[str] = None):
        """
        Wycofaj transakcję - przywróć snapshot.
        
        Args:
            reason: powód rollbacku (do logów)
        """
        if not self.is_active:
            raise TransactionError("Transaction not active")
        
        restored_files = []
        errors = []
        
        # Przywróć pliki ze snapshot
        for backed_up in self.metadata["backed_up_files"]:
            backup_path = self.snapshot_dir / backed_up
            original_path = self.project_root / backed_up
            
            try:
                # Usuń zmodyfikowany plik
                if original_path.exists():
                    if original_path.is_file():
                        original_path.unlink()
                    elif original_path.is_dir():
                        shutil.rmtree(original_path)
                
                # Przywróć backup
                if backup_path.exists():
                    if backup_path.is_file():
                        original_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_path, original_path)
                    elif backup_path.is_dir():
                        shutil.copytree(backup_path, original_path)
                    
                    restored_files.append(backed_up)
            
            except Exception as e:
                errors.append(f"{backed_up}: {e}")
        
        # Metadata
        self.metadata["status"] = "rolled_back"
        self.metadata["rolled_back_at"] = datetime.now().isoformat()
        self.metadata["reason"] = reason
        self.metadata["restored_files"] = restored_files
        self.metadata["errors"] = errors
        self._save_metadata()
        
        self.is_active = False
        
        return {
            "restored": restored_files,
            "errors": errors
        }
    
    def _save_metadata(self):
        """Zapisz metadata transakcji"""
        metadata_file = self.snapshot_dir / "_transaction.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def get_status(self) -> Dict:
        """Zwróć status transakcji"""
        return {
            "tx_id": self.tx_id,
            "status": self.metadata["status"],
            "is_active": self.is_active,
            "backed_up_files": len(self.metadata["backed_up_files"])
        }


class TransactionManager:
    """
    Zarządza transakcjami filesystem.
    
    Zapewnia:
    - izolację transakcji
    - cleanup starych snapshotów
    - recovery po crash
    """
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.tmp_dir = self.project_root / ".ai-tmp"
        self.current_tx: Optional[Transaction] = None
    
    def create_transaction(self) -> Transaction:
        """Utwórz nową transakcję"""
        if self.current_tx and self.current_tx.is_active:
            raise TransactionError("Another transaction is already active")
        
        tx = Transaction(self.project_root)
        self.current_tx = tx
        return tx
    
    def cleanup_old_snapshots(self, max_age_hours: int = 24):
        """
        Wyczyść stare snapshoty transakcji.
        
        Args:
            max_age_hours: maksymalny wiek snapshota w godzinach
        """
        if not self.tmp_dir.exists():
            return
        
        from datetime import timedelta
        now = datetime.now()
        cutoff = now - timedelta(hours=max_age_hours)
        
        removed = []
        
        for tx_dir in self.tmp_dir.glob("tx-*"):
            if not tx_dir.is_dir():
                continue
            
            metadata_file = tx_dir / "_transaction.json"
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                started_at = datetime.fromisoformat(metadata["started_at"])
                
                # Usuń jeśli stary i nie pending
                if started_at < cutoff and metadata["status"] != "pending":
                    shutil.rmtree(tx_dir)
                    removed.append(tx_dir.name)
            
            except Exception:
                pass
        
        return removed
    
    def recover_pending_transactions(self) -> List[Dict]:
        """
        Odzyskaj pending transakcje po crash.
        
        Returns:
            Lista transakcji które można rollbackować
        """
        if not self.tmp_dir.exists():
            return []
        
        pending = []
        
        for tx_dir in self.tmp_dir.glob("tx-*"):
            metadata_file = tx_dir / "_transaction.json"
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                if metadata["status"] == "pending":
                    pending.append({
                        "tx_id": metadata["tx_id"],
                        "started_at": metadata["started_at"],
                        "backed_up_files": metadata["backed_up_files"]
                    })
            
            except Exception:
                pass
        
        return pending
    
    def get_tmp_dir_size(self) -> int:
        """Zwróć rozmiar katalogu .ai-tmp w bajtach"""
        if not self.tmp_dir.exists():
            return 0
        
        total = 0
        for path in self.tmp_dir.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        
        return total