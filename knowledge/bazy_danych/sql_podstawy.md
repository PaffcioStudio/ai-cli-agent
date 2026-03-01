# Bazy danych – SQL i zarządzanie

## PostgreSQL – podstawy

### Połączenie i podstawy
```bash
psql -U postgres                    # połącz jako superuser
psql -U user -d baza -h localhost   # połącz z parametrami
psql -U user -d baza -c "SELECT 1"  # wykonaj polecenie
```

### Polecenia psql (wewnątrz sesji)
```sql
\l                                  -- lista baz danych
\c nazwa_bazy                       -- przełącz bazę
\dt                                 -- lista tabel
\dt schema.*                        -- tabele w schemacie
\d nazwa_tabeli                     -- struktura tabeli
\du                                 -- lista użytkowników
\q                                  -- wyjdź
\timing                             -- mierz czas zapytań
\x                                  -- tryb rozszerzony (expanded)
\copy tabela TO 'plik.csv' CSV HEADER  -- eksport do CSV
```

### SQL – podstawowe operacje
```sql
-- Tworzenie tabeli
CREATE TABLE uzytkownicy (
    id SERIAL PRIMARY KEY,
    imie VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    wiek INTEGER CHECK (wiek >= 0),
    data_rejestracji TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRUD
INSERT INTO uzytkownicy (imie, email, wiek) VALUES ('Jan', 'jan@example.com', 30);
SELECT * FROM uzytkownicy WHERE wiek > 25 ORDER BY imie;
UPDATE uzytkownicy SET wiek = 31 WHERE id = 1;
DELETE FROM uzytkownicy WHERE id = 1;

-- JOIN
SELECT u.imie, z.tytul
FROM uzytkownicy u
JOIN zamowienia z ON u.id = z.uzytkownik_id
WHERE u.wiek > 25;

-- Agregacje
SELECT COUNT(*), AVG(wiek), MAX(wiek) FROM uzytkownicy;
SELECT miasto, COUNT(*) FROM uzytkownicy GROUP BY miasto HAVING COUNT(*) > 5;

-- Indeksy
CREATE INDEX idx_email ON uzytkownicy(email);
CREATE INDEX idx_wielokolumnowy ON tabela(kolumna1, kolumna2);
EXPLAIN ANALYZE SELECT * FROM uzytkownicy WHERE email = 'jan@example.com';
```

### Zarządzanie PostgreSQL
```bash
# Backup i restore
pg_dump -U postgres -d baza > backup.sql          # eksport
pg_dump -U postgres -Fc -d baza > backup.dump     # format custom
pg_restore -U postgres -d baza backup.dump        # przywróć
psql -U postgres -d baza < backup.sql             # przywróć SQL

# Użytkownicy i uprawnienia
CREATE USER myuser WITH PASSWORD 'haslo';
CREATE DATABASE mydb OWNER myuser;
GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
REVOKE ALL ON tabela FROM user;
```

## MySQL/MariaDB

```bash
mysql -u root -p                    # logowanie
mysql -u user -p baza               # połącz z bazą
mysqldump -u root -p baza > backup.sql    # backup
mysql -u root -p baza < backup.sql        # restore
```

```sql
SHOW DATABASES;
USE nazwa_bazy;
SHOW TABLES;
DESCRIBE tabela;
SHOW CREATE TABLE tabela;

-- Użytkownicy
CREATE USER 'user'@'localhost' IDENTIFIED BY 'haslo';
GRANT ALL ON baza.* TO 'user'@'localhost';
FLUSH PRIVILEGES;
```

## SQLite – lekka baza lokalna

```bash
sqlite3 baza.db                     # otwórz lub utwórz bazę
sqlite3 baza.db "SELECT * FROM tabela;"  # jednorazowe zapytanie
```

```sql
.tables                             -- lista tabel
.schema tabela                      -- struktura tabeli
.headers on                         -- nagłówki kolumn
.mode column                        -- tryb kolumnowy
.output plik.csv                    -- eksportuj do pliku
.quit                               -- wyjdź
```

## Redis – baza klucz-wartość (cache)

```bash
redis-cli                           # połącz
redis-cli -h 127.0.0.1 -p 6379
redis-cli PING                      # test połączenia (odpowiedź: PONG)

# Podstawowe operacje
SET klucz "wartość"                 # ustaw
GET klucz                           # pobierz
DEL klucz                           # usuń
EXISTS klucz                        # czy istnieje?
EXPIRE klucz 3600                   # wygaśnięcie w sekundach
TTL klucz                           # czas do wygaśnięcia
KEYS wzorzec*                       # lista kluczy (uważaj na produkcji!)
FLUSHDB                             # wyczyść bazę

# Struktury danych
HSET hash pole wartość              # hashmapa
HGET hash pole
HGETALL hash
LPUSH lista wartość                 # lista (push od lewej)
RPUSH lista wartość                 # lista (push od prawej)
LRANGE lista 0 -1                   # wszystkie elementy
SADD zbiór wartość                  # zbiór
SMEMBERS zbiór
ZADD sorted_set wynik wartość       # posortowany zbiór
ZRANGE sorted_set 0 -1 WITHSCORES
```

## Dobre praktyki baz danych

1. **Zawsze twórz indeksy** na kolumnach używanych w WHERE, JOIN, ORDER BY
2. **Używaj transakcji** dla operacji wymagających spójności: `BEGIN; ... COMMIT;`
3. **Nie przechowuj haseł plain text** – używaj bcrypt/argon2
4. **Regularne backupy** – testuj przywracanie backupów
5. **Użyj connection pooling** – pgBouncer (PostgreSQL)
6. **Unikaj SELECT \*** – pobieraj tylko potrzebne kolumny
7. **EXPLAIN ANALYZE** – analizuj wolne zapytania
8. **Osobne użytkownicy** – aplikacja nie powinna mieć uprawnień superuser
