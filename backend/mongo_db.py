import os
from datetime import datetime, date
from pymongo import MongoClient, ReturnDocument, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, PyMongoError, DuplicateKeyError

class MongoDB:
    def __init__(self, uri=None, db_name="sports_platform"):
        self.uri = uri or os.environ.get("MONGO_URI", "")
        self.db_name = db_name
        self.client = None
        self.db = None
        self.is_connected = False

    def connect(self, timeout_ms=5000):
        if not self.uri or "<CLUSTER_HOST>" in self.uri:
            print("MongoDB URI not fully configured (missing cluster hostname).")
            self.is_connected = False
            return False
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=timeout_ms)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.is_connected = True
            self._ensure_indexes()
            print("Successfully connected to MongoDB Atlas!")
            return True
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
            self.is_connected = False
            return False

    def get_next_sequence(self, name):
        doc = self.db.counters.find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return doc["seq"]

    def _ensure_indexes(self):
        if not self.is_connected:
            return
        self.db.users.create_index("email", unique=True)
        self.db.tournaments.create_index([("date", ASCENDING)])
        self.db.registrations.create_index([("user_id", ASCENDING), ("tournament_id", ASCENDING)], unique=True)
        self.db.comments.create_index([("tournament_id", ASCENDING)])
        self.db.teams.create_index([("sport", ASCENDING)])
        self.db.team_requests.create_index([("team_id", ASCENDING), ("user_id", ASCENDING)], unique=True)

        # TURF FINDER & OWNER INDEXES
        self.db.turfs.create_index([("sport", ASCENDING)])
        self.db.turfs.create_index([("owner_id", ASCENDING)])
        self.db.turf_bookings.create_index([
            ("turf_id", ASCENDING),
            ("booking_date", ASCENDING),
            ("time_slot", ASCENDING)
        ], unique=True)

    # --- USER OPERATIONS ---
    def get_user_by_id(self, user_id):
        if not self.is_connected:
            return None
        return self.db.users.find_one({"id": int(user_id)})

    def get_user_by_email(self, email):
        if not self.is_connected:
            return None
        return self.db.users.find_one({"email": email.lower().strip()})

    def create_user(self, name, email, password_hash, role='player', latitude=None, longitude=None):
        user_id = self.get_next_sequence("users")
        doc = {
            "_id": user_id,
            "id": user_id,
            "name": name,
            "email": email.lower().strip(),
            "password": password_hash,
            "role": role,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": datetime.utcnow().isoformat()
        }
        self.db.users.insert_one(doc)
        return doc

    # --- TOURNAMENT OPERATIONS ---
    def get_tournament_by_id(self, tournament_id):
        if not self.is_connected:
            return None
        return self.db.tournaments.find_one({"id": int(tournament_id)})

    def get_tournaments(self, sport=None):
        if not self.is_connected:
            return []
        query = {}
        if sport:
            query["sport"] = {"$regex": f"^{sport}$", "$options": "i"}
        return list(self.db.tournaments.find(query).sort("date", ASCENDING))

    def create_tournament(self, name, sport, date, entry_fee, mode, latitude, longitude,
                          organizer_id=None, venue_name=None, venue_address=None,
                          organizer_phone=None, youtube_link=None, organizer_verified=False):
        t_id = self.get_next_sequence("tournaments")
        doc = {
            "_id": t_id,
            "id": t_id,
            "name": name,
            "sport": sport,
            "date": date,
            "entry_fee": float(entry_fee),
            "mode": mode,
            "latitude": float(latitude) if latitude is not None else None,
            "longitude": float(longitude) if longitude is not None else None,
            "organizer_id": organizer_id,
            "venue_name": venue_name or name,
            "venue_address": venue_address or "Address not provided",
            "organizer_phone": organizer_phone,
            "youtube_link": youtube_link,
            "organizer_verified": bool(organizer_verified)
        }
        self.db.tournaments.insert_one(doc)
        return doc

    # --- TEAM OPERATIONS ---
    def create_team(self, name, sport, skill_level, created_by, latitude=None, longitude=None):
        team_id = self.get_next_sequence("teams")
        doc = {
            "_id": team_id,
            "id": team_id,
            "name": name,
            "sport": sport,
            "skill_level": skill_level or "Intermediate",
            "created_by": int(created_by),
            "latitude": float(latitude) if latitude is not None else None,
            "longitude": float(longitude) if longitude is not None else None,
            "created_at": datetime.utcnow().isoformat()
        }
        self.db.teams.insert_one(doc)
        return doc

    def get_teams(self, sport=None):
        if not self.is_connected:
            return []
        query = {}
        if sport:
            query["sport"] = {"$regex": f"^{sport}$", "$options": "i"}
        teams = list(self.db.teams.find(query))
        results = []
        for t in teams:
            creator = self.get_user_by_id(t["created_by"])
            member_count = self.db.team_requests.count_documents({"team_id": t["id"], "status": "approved"}) + 1
            results.append({
                "id": t["id"],
                "name": t["name"],
                "sport": t["sport"],
                "skill_level": t.get("skill_level", "Intermediate"),
                "created_by": t["created_by"],
                "creator_name": creator["name"] if creator else "Captain",
                "creator_email": creator["email"] if creator else "",
                "members_count": member_count,
                "latitude": t.get("latitude"),
                "longitude": t.get("longitude")
            })
        return results

    def get_team_by_id(self, team_id):
        if not self.is_connected:
            return None
        return self.db.teams.find_one({"id": int(team_id)})

    def create_team_request(self, team_id, user_id):
        existing = self.db.team_requests.find_one({"team_id": int(team_id), "user_id": int(user_id)})
        if existing:
            return existing
        req_id = self.get_next_sequence("team_requests")
        doc = {
            "_id": req_id,
            "id": req_id,
            "team_id": int(team_id),
            "user_id": int(user_id),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        self.db.team_requests.insert_one(doc)
        return doc

    def get_team_requests(self, team_id):
        if not self.is_connected:
            return []
        reqs = list(self.db.team_requests.find({"team_id": int(team_id)}))
        results = []
        for r in reqs:
            user = self.get_user_by_id(r["user_id"])
            results.append({
                "id": r["id"],
                "team_id": r["team_id"],
                "user_id": r["user_id"],
                "user_name": user["name"] if user else "Player",
                "user_email": user["email"] if user else "",
                "status": r["status"]
            })
        return results

    def update_team_request_status(self, request_id, status):
        if not self.is_connected:
            return False
        self.db.team_requests.update_one({"id": int(request_id)}, {"$set": {"status": status}})
        return True

    def get_user_team_requests(self, user_id):
        if not self.is_connected:
            return []
        reqs = list(self.db.team_requests.find({"user_id": int(user_id)}))
        results = []
        for r in reqs:
            t = self.get_team_by_id(r["team_id"])
            if t:
                results.append({
                    "request_id": r["id"],
                    "team_id": t["id"],
                    "team_name": t["name"],
                    "sport": t["sport"],
                    "status": r["status"]
                })
        return results

    # --- TURF FINDER & TURF OWNER OPERATIONS ---
    def create_turf(self, name, owner_id, sport, address, latitude, longitude, price_per_hour,
                    rating=4.8, facilities=None, rules=None, image_url=None, opening_time="06:00", closing_time="23:00"):
        turf_id = self.get_next_sequence("turfs")
        if facilities is None:
            facilities = ["Floodlights", "Changing Room", "Parking", "Drinking Water"]
        doc = {
            "_id": turf_id,
            "id": turf_id,
            "name": name,
            "owner_id": int(owner_id),
            "sport": sport,
            "address": address,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "price_per_hour": float(price_per_hour),
            "rating": float(rating),
            "facilities": facilities if isinstance(facilities, list) else [f.strip() for f in str(facilities).split(',')],
            "rules": rules or "Standard turf rules apply. Please arrive 10 minutes prior to slot.",
            "image_url": image_url or "https://images.unsplash.com/photo-1529900748604-07564a03e7a6?auto=format&fit=crop&w=600&q=80",
            "opening_time": opening_time,
            "closing_time": closing_time,
            "created_at": datetime.utcnow().isoformat()
        }
        self.db.turfs.insert_one(doc)
        return doc

    def get_turfs(self, sport=None, max_price=None, facility=None):
        if not self.is_connected:
            return []
        query = {}
        if sport:
            query["sport"] = {"$regex": f"^{sport}$", "$options": "i"}
        if max_price:
            try:
                query["price_per_hour"] = {"$lte": float(max_price)}
            except (ValueError, TypeError):
                pass
        if facility:
            query["facilities"] = {"$regex": f"^{facility}$", "$options": "i"}

        return list(self.db.turfs.find(query))

    def get_turf_by_id(self, turf_id):
        if not self.is_connected:
            return None
        return self.db.turfs.find_one({"id": int(turf_id)})

    def get_turf_slots(self, turf_id, booking_date):
        turf = self.get_turf_by_id(turf_id)
        if not turf:
            return []

        start_h = int(turf.get("opening_time", "06:00").split(":")[0])
        end_h = int(turf.get("closing_time", "23:00").split(":")[0])

        existing_bookings = list(self.db.turf_bookings.find({
            "turf_id": int(turf_id),
            "booking_date": booking_date,
            "status": {"$in": ["confirmed", "blocked_by_owner"]}
        }))

        booked_slots = {b["time_slot"]: b["status"] for b in existing_bookings}

        slots = []
        for h in range(start_h, end_h):
            slot_str = f"{h:02d}:00 - {h+1:02d}:00"
            status = booked_slots.get(slot_str, "available")
            slots.append({
                "time_slot": slot_str,
                "status": status,
                "price": turf["price_per_hour"]
            })
        return slots

    def create_turf_booking(self, turf_id, user_id, booking_date, time_slot, total_price, status="confirmed"):
        # Double booking prevention check
        existing = self.db.turf_bookings.find_one({
            "turf_id": int(turf_id),
            "booking_date": booking_date,
            "time_slot": time_slot,
            "status": {"$in": ["confirmed", "blocked_by_owner"]}
        })
        if existing:
            raise ValueError("Slot already booked for this time.")

        b_id = self.get_next_sequence("turf_bookings")
        doc = {
            "_id": b_id,
            "id": b_id,
            "turf_id": int(turf_id),
            "user_id": int(user_id),
            "booking_date": booking_date,
            "time_slot": time_slot,
            "total_price": float(total_price),
            "status": status,
            "created_at": datetime.utcnow().isoformat()
        }

        try:
            self.db.turf_bookings.insert_one(doc)
            return doc
        except DuplicateKeyError:
            raise ValueError("Slot already booked for this time.")

    def cancel_turf_booking(self, booking_id, user_id):
        b = self.db.turf_bookings.find_one({"id": int(booking_id)})
        if not b:
            return False, "Booking not found"

        turf = self.get_turf_by_id(b["turf_id"])
        is_owner = turf and turf["owner_id"] == int(user_id)
        is_player = b["user_id"] == int(user_id)

        if not (is_owner or is_player):
            return False, "Unauthorized to cancel booking"

        self.db.turf_bookings.update_one({"id": int(booking_id)}, {"$set": {"status": "cancelled"}})
        return True, "Booking cancelled successfully"

    def get_user_turf_bookings(self, user_id):
        if not self.is_connected:
            return []
        bookings = list(self.db.turf_bookings.find({"user_id": int(user_id)}).sort("created_at", DESCENDING))
        results = []
        for b in bookings:
            t = self.get_turf_by_id(b["turf_id"])
            if t:
                results.append({
                    "id": b["id"],
                    "turf_id": t["id"],
                    "turf_name": t["name"],
                    "sport": t["sport"],
                    "address": t["address"],
                    "booking_date": b["booking_date"],
                    "time_slot": b["time_slot"],
                    "total_price": b["total_price"],
                    "status": b["status"],
                    "created_at": b["created_at"]
                })
        return results

    def get_owner_turfs(self, owner_id):
        if not self.is_connected:
            return []
        return list(self.db.turfs.find({"owner_id": int(owner_id)}))

    def get_owner_bookings(self, owner_id):
        if not self.is_connected:
            return []
        turfs = self.get_owner_turfs(owner_id)
        t_ids = [t["id"] for t in turfs]
        t_map = {t["id"]: t for t in turfs}

        bookings = list(self.db.turf_bookings.find({"turf_id": {"$in": t_ids}}).sort("created_at", DESCENDING))
        results = []
        for b in bookings:
            user = self.get_user_by_id(b["user_id"])
            t = t_map.get(b["turf_id"])
            results.append({
                "id": b["id"],
                "turf_id": b["turf_id"],
                "turf_name": t["name"] if t else "Turf",
                "customer_name": user["name"] if user else "Player",
                "customer_email": user["email"] if user else "",
                "booking_date": b["booking_date"],
                "time_slot": b["time_slot"],
                "total_price": b["total_price"],
                "status": b["status"],
                "created_at": b["created_at"]
            })
        return results

    def get_owner_revenue_stats(self, owner_id):
        bookings = self.get_owner_bookings(owner_id)
        confirmed = [b for b in bookings if b["status"] == "confirmed"]
        total_revenue = sum(b["total_price"] for b in confirmed)
        total_bookings = len(confirmed)
        return {
            "total_revenue": total_revenue,
            "total_bookings": total_bookings,
            "total_turfs": len(self.get_owner_turfs(owner_id))
        }

    # --- REGISTRATION OPERATIONS ---
    def get_registration(self, user_id, tournament_id):
        if not self.is_connected:
            return None
        return self.db.registrations.find_one({"user_id": int(user_id), "tournament_id": int(tournament_id)})

    def create_registration(self, user_id, tournament_id, team_id=None):
        r_id = self.get_next_sequence("registrations")
        doc = {
            "_id": r_id,
            "id": r_id,
            "user_id": int(user_id),
            "tournament_id": int(tournament_id),
            "team_id": int(team_id) if team_id else None,
            "created_at": datetime.utcnow().isoformat()
        }
        self.db.registrations.insert_one(doc)
        return doc

    def get_user_registrations(self, user_id):
        if not self.is_connected:
            return []
        regs = list(self.db.registrations.find({"user_id": int(user_id)}))
        results = []
        for r in regs:
            t = self.get_tournament_by_id(r["tournament_id"])
            if t:
                results.append({
                    "registration_id": r["id"],
                    "tournament_id": t["id"],
                    "name": t["name"],
                    "sport": t["sport"],
                    "date": t["date"],
                    "entry_fee": t["entry_fee"],
                    "mode": t["mode"]
                })
        return results

    def get_organizer_registrations(self, organizer_id):
        if not self.is_connected:
            return []
        org_tournaments = list(self.db.tournaments.find({"organizer_id": int(organizer_id)}))
        t_ids = [t["id"] for t in org_tournaments]
        t_map = {t["id"]: t for t in org_tournaments}

        regs = list(self.db.registrations.find({"tournament_id": {"$in": t_ids}}))
        grouped = {}
        for r in regs:
            t = t_map.get(r["tournament_id"])
            player = self.get_user_by_id(r["user_id"])
            if not t or not player:
                continue

            if t["id"] not in grouped:
                grouped[t["id"]] = {
                    "tournament_id": t["id"],
                    "name": t["name"],
                    "sport": t["sport"],
                    "mode": t["mode"],
                    "date": t["date"],
                    "registrations": []
                }

            grouped[t["id"]]["registrations"].append({
                "registration_id": r["id"],
                "user_id": player["id"],
                "user_name": player["name"],
                "user_email": player["email"],
                "team_id": r.get("team_id")
            })

        return list(grouped.values())

    # --- COMMENT OPERATIONS ---
    def get_tournament_comments(self, tournament_id):
        if not self.is_connected:
            return []
        comments = list(self.db.comments.find({"tournament_id": int(tournament_id)}).sort("created_at", DESCENDING))
        results = []
        for c in comments:
            user = self.get_user_by_id(c["user_id"])
            results.append({
                "id": c["id"],
                "tournament_id": c["tournament_id"],
                "user_id": c["user_id"],
                "user_name": user["name"] if user else "Anonymous",
                "comment_text": c["comment_text"],
                "created_at": c["created_at"]
            })
        return results

    def add_comment(self, tournament_id, user_id, comment_text):
        c_id = self.get_next_sequence("comments")
        doc = {
            "_id": c_id,
            "id": c_id,
            "tournament_id": int(tournament_id),
            "user_id": int(user_id),
            "comment_text": comment_text,
            "created_at": datetime.utcnow().isoformat()
        }
        self.db.comments.insert_one(doc)
        return doc
