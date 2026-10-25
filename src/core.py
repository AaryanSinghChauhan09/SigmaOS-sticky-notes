"""Sticky notes store for SigmaOS-sticky-notes (inspired by linuxmint/sticky).

Principles: a small JSON-backed note store, monotonic ids, pinned-first
ordering, fail-fast on unknown ids and empty text, case-insensitive search
with deterministic ordering, atomic writes.
"""
import argparse, json, os, sys, tempfile, time

ENGINE = {
    "name": "sigma-sticky",
    "summary": "Sticky notes: add, list, edit, pin, search",
    "language": "python",
    "verbs": ["add", "list", "edit", "pin", "search"],
    "principles": ["Encapsulation", "Least Astonishment", "Fail-Fast", "KISS",
                   "DRY", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-sticky add "buy milk"
added note 1
$ sigma-sticky add "ship SigmaOS" --pin
$ sigma-sticky list
$ sigma-sticky edit 1 --text "buy oat milk"
$ sigma-sticky search milk
"""

DEFAULT_STORE = os.path.expanduser("~/.local/share/sigma-sticky/notes.json")


class StickyError(ValueError):
    pass


def empty_store():
    return {"next_id": 1, "notes": []}


def load_store(path):
    """Load the note store; fail-fast on corruption."""
    if not os.path.exists(path):
        return empty_store()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data.get("notes"), list) or "next_id" not in data:
        raise StickyError(f"corrupt store: {path}")
    for n in data["notes"]:
        if not isinstance(n.get("id"), int) or not isinstance(n.get("text"), str):
            raise StickyError(f"corrupt note in {path}")
    return data


def save_store(path, store):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".sigma-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def add_note(store, text, pinned=False, now=None):
    """Append a note; returns the new note dict."""
    text = str(text).strip()
    if not text:
        raise StickyError("empty note text")
    note = {"id": store["next_id"], "text": text, "pinned": bool(pinned),
            "created": now if now is not None else time.time()}
    store["next_id"] += 1
    store["notes"].append(note)
    return note


def _find(store, nid):
    for n in store["notes"]:
        if n["id"] == nid:
            return n
    raise StickyError(f"no such note: {nid}")


def list_notes(store, pinned_only=False):
    """Pinned first, then by id (deterministic)."""
    notes = [n for n in store["notes"] if not pinned_only or n["pinned"]]
    return sorted(notes, key=lambda n: (not n["pinned"], n["id"]))


def edit_note(store, nid, text):
    text = str(text).strip()
    if not text:
        raise StickyError("empty note text")
    note = _find(store, nid)
    note["text"] = text
    return note


def pin_note(store, nid, pinned=True):
    note = _find(store, nid)
    note["pinned"] = bool(pinned)
    return note


def delete_note(store, nid):
    note = _find(store, nid)
    store["notes"].remove(note)
    return note


def search_notes(store, query):
    """Case-insensitive substring search; matches ordered by id."""
    q = str(query).strip().lower()
    if not q:
        raise StickyError("empty query")
    return [n for n in sorted(store["notes"], key=lambda n: n["id"])
            if q in n["text"].lower()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    p.add_argument("--store", default=DEFAULT_STORE, help="notes store (JSON)")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add a note")
    a.add_argument("text")
    a.add_argument("--pin", action="store_true")
    ls = sub.add_parser("list", help="list notes (pinned first)")
    ls.add_argument("--pinned-only", action="store_true")
    ed = sub.add_parser("edit", help="replace a note's text")
    ed.add_argument("id", type=int)
    ed.add_argument("--text", required=True)
    pn = sub.add_parser("pin", help="pin or unpin a note")
    pn.add_argument("id", type=int)
    pn.add_argument("--off", action="store_true", help="unpin instead")
    rm = sub.add_parser("delete", help="delete a note")
    rm.add_argument("id", type=int)
    se = sub.add_parser("search", help="search notes (case-insensitive)")
    se.add_argument("query")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = load_store(args.store)
        if args.cmd == "add":
            note = add_note(store, args.text, pinned=args.pin)
            save_store(args.store, store)
            print(f"added note {note['id']}")
        elif args.cmd == "list":
            notes = list_notes(store, pinned_only=args.pinned_only)
            if not notes:
                print("(no notes)")
            for n in notes:
                mark = "*" if n["pinned"] else " "
                print(f"{mark} {n['id']}: {n['text']}")
        elif args.cmd == "edit":
            note = edit_note(store, args.id, args.text)
            save_store(args.store, store)
            print(f"edited note {note['id']}")
        elif args.cmd == "pin":
            note = pin_note(store, args.id, pinned=not args.off)
            save_store(args.store, store)
            print(f"note {note['id']} pinned={'true' if note['pinned'] else 'false'}")
        elif args.cmd == "delete":
            note = delete_note(store, args.id)
            save_store(args.store, store)
            print(f"deleted note {note['id']}")
        elif args.cmd == "search":
            hits = search_notes(store, args.query)
            if not hits:
                print("no matches")
            for n in hits:
                print(f"{n['id']}: {n['text']}")
        return 0
    except (StickyError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "notes.json")
        store = load_store(path)                  # missing store -> empty
        assert store == empty_store()
        # add + persistence across a reload (the store really persists)
        n1 = add_note(store, "buy milk", now=1000.0)
        n2 = add_note(store, "ship SigmaOS", pinned=True, now=1001.0)
        assert (n1["id"], n2["id"]) == (1, 2)
        save_store(path, store)
        again = load_store(path)
        assert [n["text"] for n in list_notes(again)] == ["ship SigmaOS", "buy milk"]
        # ids never reused after reload
        n3 = add_note(again, "third", now=1002.0)
        assert n3["id"] == 3
        # pinned-first ordering is deterministic
        assert [n["id"] for n in list_notes(again)] == [2, 1, 3]
        pin_note(again, 1, pinned=True)
        assert [n["id"] for n in list_notes(again)] == [1, 2, 3]
        assert [n["id"] for n in list_notes(again, pinned_only=True)] == [1, 2]
        # edit
        edit_note(again, 3, "THIRD note")
        assert again["notes"][2]["text"] == "THIRD note"
        # search: case-insensitive, ordered by id
        assert [n["id"] for n in search_notes(again, "MILK")] == [1]
        assert [n["id"] for n in search_notes(again, "note")] == [3]
        assert search_notes(again, "zzz") == []
        # fail-fast paths
        for bad in (lambda: add_note(again, "   "),
                    lambda: edit_note(again, 3, ""),
                    lambda: edit_note(again, 99, "x"),
                    lambda: pin_note(again, 99),
                    lambda: delete_note(again, 99),
                    lambda: search_notes(again, " ")):
            try:
                bad()
            except StickyError:
                pass
            else:
                raise AssertionError("expected StickyError")
        # delete + persist final state
        delete_note(again, 2)
        assert [n["id"] for n in list_notes(again)] == [1, 3]
        save_store(path, again)
        final = load_store(path)
        assert [n["id"] for n in list_notes(final)] == [1, 3]
        assert final["next_id"] == 4
        # corrupt store fail-fast
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"next_id": 1, "notes": [{"id": "x"}]}')
        try:
            load_store(path)
        except StickyError:
            pass
        else:
            raise AssertionError("corrupt store not caught")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
