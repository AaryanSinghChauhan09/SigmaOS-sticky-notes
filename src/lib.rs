//! SigmaOS-sticky-notes — desktop sticky notes (Linux Mint `sticky` parity).
//!
//! Note model with color, position, size, lock, and z-order; manager
//! supports CRUD, serialization to a simple line format, and per-note
//! opacity stacking. Pure logic — rendering is the shell's job.

use std::collections::BTreeMap;

/// Sticky note colors (Mint sticky palette).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NoteColor {
    Yellow,
    Pink,
    Blue,
    Green,
}

impl NoteColor {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Yellow => "yellow",
            Self::Pink => "pink",
            Self::Blue => "blue",
            Self::Green => "green",
        }
    }
    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "yellow" => Some(Self::Yellow),
            "pink" => Some(Self::Pink),
            "blue" => Some(Self::Blue),
            "green" => Some(Self::Green),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct StickyNote {
    pub id: u64,
    pub text: String,
    pub color: NoteColor,
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    /// Higher = on top.
    pub z_order: u32,
    pub locked: bool,
    pub opacity: u8, // 0-100
}

impl StickyNote {
    pub fn new(id: u64, text: &str) -> Self {
        Self {
            id,
            text: text.into(),
            color: NoteColor::Yellow,
            x: 0,
            y: 0,
            width: 200,
            height: 150,
            z_order: 0,
            locked: false,
            opacity: 100,
        }
    }
}

#[derive(Debug, Default)]
pub struct StickyNotesManager {
    notes: BTreeMap<u64, StickyNote>,
    next_id: u64,
    top_z: u32,
}

impl StickyNotesManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_note(&mut self, text: &str, color: NoteColor) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        self.top_z += 1;
        self.notes.insert(
            id,
            StickyNote {
                id,
                text: text.into(),
                color,
                z_order: self.top_z,
                ..StickyNote::new(id, text)
            },
        );
        id
    }

    pub fn get(&self, id: u64) -> Option<&StickyNote> {
        self.notes.get(&id)
    }

    pub fn get_mut(&mut self, id: u64) -> Option<&mut StickyNote> {
        self.notes.get_mut(&id)
    }

    pub fn remove(&mut self, id: u64) -> bool {
        self.notes.remove(&id).is_some()
    }

    /// Update text; returns false if note is locked.
    pub fn update_text(&mut self, id: u64, text: &str) -> bool {
        if let Some(n) = self.notes.get_mut(&id) {
            if n.locked {
                return false;
            }
            n.text = text.into();
            true
        } else {
            false
        }
    }

    /// Move note; locked notes reject moves.
    pub fn move_note(&mut self, id: u64, x: i32, y: i32) -> bool {
        if let Some(n) = self.notes.get_mut(&id) {
            if n.locked {
                return false;
            }
            n.x = x;
            n.y = y;
            true
        } else {
            false
        }
    }

    /// Bring note to front (z-order top).
    pub fn raise(&mut self, id: u64) {
        self.top_z += 1;
        if let Some(n) = self.notes.get_mut(&id) {
            n.z_order = self.top_z;
        }
    }

    /// Notes sorted back-to-front for painting.
    pub fn paint_order(&self) -> Vec<&StickyNote> {
        let mut v: Vec<&StickyNote> = self.notes.values().collect();
        v.sort_by_key(|n| n.z_order);
        v
    }

    pub fn count(&self) -> usize {
        self.notes.len()
    }

    /// Serialize to a compact line format:
    /// `id|color|x|y|w|h|z|locked|opacity|text`
    pub fn serialize(&self) -> String {
        let mut out = String::new();
        for n in self.notes.values() {
            out.push_str(&format!(
                "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}\n",
                n.id,
                n.color.as_str(),
                n.x,
                n.y,
                n.width,
                n.height,
                n.z_order,
                n.locked as u8,
                n.opacity,
                n.text.replace('\n', "\\n")
            ));
        }
        out
    }

    /// Parse serialized notes back; skips malformed lines.
    pub fn deserialize(data: &str) -> Self {
        let mut mgr = Self::new();
        for line in data.lines() {
            let f: Vec<&str> = line.split('|').collect();
            if f.len() < 10 {
                continue;
            }
            let (Ok(id), Some(color)) = (f[0].parse::<u64>(), NoteColor::from_str(f[1])) else {
                continue;
            };
            let num = |i: usize| f.get(i).and_then(|s| s.parse().ok()).unwrap_or(0);
            let locked = f[7].parse::<u8>().unwrap_or(0) != 0;
            let opacity = (num(8) as u8).min(100);
            let text = f[9..].join("|").replace("\\n", "\n");
            let z = num(6) as u32;
            mgr.notes.insert(
                id,
                StickyNote {
                    id,
                    text,
                    color,
                    x: num(2) as i32,
                    y: num(3) as i32,
                    width: num(4) as u32,
                    height: num(5) as u32,
                    z_order: z,
                    locked,
                    opacity,
                },
            );
            mgr.next_id = mgr.next_id.max(id + 1);
            mgr.top_z = mgr.top_z.max(z);
        }
        mgr
    }
}

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_paint_order() {
        let mut m = StickyNotesManager::new();
        let a = m.add_note("first", NoteColor::Pink);
        let b = m.add_note("second", NoteColor::Blue);
        assert_eq!(m.count(), 2);
        let order = m.paint_order();
        assert_eq!(order[0].id, a);
        assert_eq!(order[1].id, b);
        m.raise(a);
        assert_eq!(m.paint_order().last().unwrap().id, a);
    }

    #[test]
    fn lock_blocks_edit_and_move() {
        let mut m = StickyNotesManager::new();
        let id = m.add_note("note", NoteColor::Green);
        m.get_mut(id).unwrap().locked = true;
        assert!(!m.update_text(id, "changed"));
        assert!(!m.move_note(id, 10, 10));
        assert_eq!(m.get(id).unwrap().text, "note");
    }

    #[test]
    fn serialize_roundtrip() {
        let mut m = StickyNotesManager::new();
        let id = m.add_note("line1\nline2", NoteColor::Yellow);
        m.move_note(id, 50, 60);
        let data = m.serialize();
        let m2 = StickyNotesManager::deserialize(&data);
        assert_eq!(m2.count(), 1);
        let n = m2.get(id).unwrap();
        assert_eq!(n.text, "line1\nline2");
        assert_eq!(n.x, 50);
        assert_eq!(n.color, NoteColor::Yellow);
    }

    #[test]
    fn malformed_lines_skipped() {
        let m = StickyNotesManager::deserialize("bad|line\n1|yellow|0|0|200|150|1|0|100|ok\n");
        assert_eq!(m.count(), 1);
    }
}
