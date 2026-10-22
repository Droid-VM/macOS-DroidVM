"""Read-only parser of an MH_FILESET kernelcache (macOS 14, arm64e): fileset entries, per-entry Mach-O, symbols, chained fixups."""
import plistlib
import struct

CHAINED_PTR_64_KERNEL_CACHE = 8


class Kernelcache:
    def __init__(self, data):
        self.data = data
        magic, cpu, sub, kind, count, size = struct.unpack_from('<6I', data, 0)
        if (magic, cpu, kind) != (0xfeedfacf, 0x100000c, 12):
            raise ValueError('not an arm64 MH_FILESET kernelcache')
        self.subtype = sub
        self.entries, self.segments, self.fixups_cmd = {}, [], None
        offset = 32
        for _ in range(count):
            command, length = struct.unpack_from('<II', data, offset)
            if command == 0x80000035:
                va, fileoff, name_at = struct.unpack_from('<QQI', data, offset + 8)
                name = data[offset + name_at:offset + length].split(b'\0')[0].decode()
                self.entries[name] = {'va': va, 'fileoff': fileoff}
            elif command == 0x19:
                self.segments.append(self.segment(offset))
            elif command == 0x80000034:
                self.fixups_cmd = struct.unpack_from('<II', data, offset + 8)
            offset += length
        self.base = min(s['va'] for s in self.segments if s['name'] == '__TEXT')

    def segment(self, offset):
        name, va, size, fileoff, filesize, maxprot, initprot, nsects, flags = struct.unpack_from('<16s4Q4I', self.data, offset + 8)
        sections = []
        for index in range(nsects):
            at = offset + 72 + index * 80
            sname, sseg, sva, ssize, sfileoff = struct.unpack_from('<16s16sQQI', self.data, at)
            sections.append({'name': sname.split(b'\0')[0].decode(), 'segment': sseg.split(b'\0')[0].decode(),
                             'va': sva, 'size': ssize, 'fileoff': sfileoff, 'command_offset': at})
        return {'name': name.split(b'\0')[0].decode(), 'va': va, 'size': size, 'fileoff': fileoff, 'filesize': filesize,
                'maxprot': maxprot, 'initprot': initprot, 'sections': sections, 'command_offset': offset}

    def macho(self, name):
        entry = self.entries[name]
        at = entry['fileoff']
        magic, cpu, sub, kind, count, size = struct.unpack_from('<6I', self.data, at)
        result = {'name': name, 'header_at': at, 'header_va': entry['va'], 'kind': kind, 'segments': [], 'symtab': None}
        offset = at + 32
        for _ in range(count):
            command, length = struct.unpack_from('<II', self.data, offset)
            if command == 0x19:
                result['segments'].append(self.segment(offset))
            elif command == 2:
                result['symtab'] = struct.unpack_from('<4I', self.data, offset + 8)
            offset += length
        return result

    def symbols(self, macho):
        """[(name, type, sect, desc, value)] of the entry's LC_SYMTAB."""
        if macho['symtab'] is None:
            return []
        symoff, count, stroff, strsize = macho['symtab']
        strings = self.data[stroff:stroff + strsize]
        out = []
        for index in range(count):
            strx, kind, sect, desc, value = struct.unpack_from('<IBBHQ', self.data, symoff + index * 16)
            end = strings.find(b'\0', strx)
            out.append((strings[strx:end].decode(errors='replace'), kind, sect, desc, value))
        return out

    def info_plist(self, macho):
        for segment in macho['segments']:
            for section in segment['sections']:
                if section['name'] == '__info_plist':
                    blob = self.data[section['fileoff']:section['fileoff'] + section['size']]
                    return plistlib.loads(blob.split(b'\0')[0])
        return None

    def file_offset(self, va, length=1):
        for segment in self.segments:
            if segment['va'] <= va and va + length <= segment['va'] + segment['filesize']:
                return segment['fileoff'] + va - segment['va']
        for entry in self.entries:
            pass
        raise ValueError(f'unbacked address {va:#x}')

    def chained_sites(self):
        """Yield (site_va, raw_value, target_va, auth, diversity, addr_div, key) for every chained rebase."""
        dataoff, datasize = self.fixups_cmd
        blob = self.data[dataoff:dataoff + datasize]
        _, starts_offset = struct.unpack_from('<II', blob, 0)
        count, = struct.unpack_from('<I', blob, starts_offset)
        offsets = struct.unpack_from(f'<{count}I', blob, starts_offset + 4)
        for index, rel in enumerate(offsets):
            if not rel:
                continue
            _, page_size, fmt, segment_offset, _, pages = struct.unpack_from('<IHHQIH', blob, starts_offset + rel)
            if fmt != CHAINED_PTR_64_KERNEL_CACHE:
                raise ValueError(f'unsupported chained pointer format {fmt}')
            starts = struct.unpack_from(f'<{pages}H', blob, starts_offset + rel + 22)
            segment = next(s for s in self.segments if s['fileoff'] == segment_offset)
            for page, start in enumerate(starts):
                if start == 0xffff:
                    continue
                if start & 0x8000:
                    raise ValueError('multi-start chain pages are not supported')
                location = segment_offset + page * page_size + start
                while True:
                    value, = struct.unpack_from('<Q', self.data, location)
                    target = self.base + (value & 0x3fffffff)
                    yield (segment['va'] + (location - segment_offset), value, target, bool(value >> 63),
                           (value >> 32) & 0xffff, bool(value >> 48 & 1), (value >> 49) & 3)
                    step = (value >> 51) & 0xfff
                    if not step:
                        break
                    location += step * 4
