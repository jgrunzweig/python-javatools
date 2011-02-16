"""

Utility for comparing two distributions.

Distributions are directories. Any JAR files (eg: jar, sar, ear, war)
will be deeply checked for their class members. And Class files will
be checked for deep differences.

"""


import sys
from change import Change, GenericChange, SuperChange, Addition, Removal
from change import squash
from change import yield_sorted_by_type
from dirdelta import fnmatches



class DistContentChange(Change):
    label = "Distributed Content Changed"


    def __init__(self, ldir, rdir, entry):
        Change.__init__(self, ldir, rdir)
        self.entry = entry
    

    def get_description(self):
        return "%s: %s" % (self.label, self.entry)


    def is_ignored(self, options):
        return fnmatches(self.entry, *options.ignore_filenames)



class DistContentAdded(DistContentChange, Addition):
    label = "Distributed Content Added"
    


class DistContentRemoved(DistContentChange, Removal):
    label = "Distributed Content Removed"



class DistJarChange(SuperChange, DistContentChange):
    label = "Distributed JAR"


    def __init__(self, ldata, rdata, entry):
        DistContentChange.__init__(self, ldata, rdata, entry)


    def collect_impl(self):
        from zipdelta import ZipFile
        from jardiff import JarChange
        from os.path import join

        lf = join(self.ldata, self.entry)
        rf = join(self.rdata, self.entry)

        yield JarChange(ZipFile(lf), ZipFile(rf))
    


class DistJarAdded(DistContentAdded):
    label = "Distributed JAR Added"



class DistJarRemoved(DistContentRemoved):
    label = "Distributed JAR Removed"



class DistClassChange(SuperChange, DistContentChange):
    label = "Distributed Java Class"


    def __init__(self, ldata, rdata, entry):
        DistContentChange.__init__(self, ldata, rdata, entry)


    def collect_impl(self):
        from javaclass import unpack_classfile
        from classdiff import JavaClassChange
        from os.path import join

        lf = join(self.ldata, self.entry)
        rf = join(self.rdata, self.entry)

        linfo = unpack_classfile(lf)
        rinfo = unpack_classfile(rf)

        yield JavaClassChange(linfo, rinfo)



class DistClassAdded(DistContentAdded):
    label = "Distributed Java Class Added"



class DistClassRemoved(DistContentRemoved):
    label = "Distributed Java Class Removed"




JAR_PATTERNS = ( "*.ear",
                 "*.jar",
                 "*.rar",
                 "*.sar",
                 "*.war", )



class DistChange(SuperChange):
    label = "Distribution"


    def __init__(self, l, r, shallow=False):
        SuperChange.__init__(self, l, r)
        self.shallow = shallow


    def get_description(self):
        return "%s %s from %s to %s" % \
            (self.label, ("unchanged","changed")[self.is_change()],
             self.ldata, self.rdata)


    @yield_sorted_by_type(DistClassAdded,
                          DistClassRemoved,
                          DistClassChange,
                          DistJarAdded,
                          DistJarRemoved,
                          DistJarChange,
                          DistContentAdded,
                          DistContentRemoved,
                          DistContentChange)
    def collect_impl(self):
        from dirdelta import compare, LEFT, RIGHT, SAME, DIFF
        from dirdelta import fnmatches

        ld, rd = self.ldata, self.rdata
        deep = not self.shallow

        for event,entry in compare(ld, rd):
            if deep and fnmatches(entry, *JAR_PATTERNS):
                if event == LEFT:
                    yield DistJarRemoved(ld, rd, entry)
                elif event == RIGHT:
                    yield DistJarAdded(ld, rd, entry)
                elif event == DIFF:
                    yield DistJarChange(ld, rd, entry)

            elif deep and fnmatches(entry, "*.class"):
                if event == LEFT:
                    yield DistClassRemoved(ld, rd, entry)
                elif event == RIGHT:
                    yield DistClassAdded(ld, rd, entry)
                elif event == DIFF:
                    yield DistClassChange(ld, rd, entry)

            else:
                if event == LEFT:
                    yield DistContentRemoved(ld, rd, entry)
                elif event == RIGHT:
                    yield DistContentAdded(ld, rd, entry)
                elif event == DIFF:
                    yield DistContentChange(ld, rd, entry)



class DistReport(DistChange):

    """ This class has side-effects. Running the check method with the
    reportdir option set to True will cause the deep checks to be
    written to file in that directory """
    

    def __init__(self, l, r, options, shallow=False):
        DistChange.__init__(self, l, r, shallow)
        self.options = options


    def check_impl(self):
        squashed = list()
        
        overall_c = False

        options = self.options

        for change in self.collect_impl():

            change.check()
            c = change.is_change()
            i = change.is_ignored(options)

            squashed.append(squash(change, c, i))
            self.report(change)

            change.clear()
            del change

            overall_c = overall_c or c

        self.change = overall_c
        self.changes = tuple(squashed)

        return overall_c, None


    def report(self, change):
        from os.path import exists, split, join
        from os import makedirs

        opts = self.options
        reportdir = getattr(opts, "report_dir", None)

        if reportdir:
            d,f = split(change.entry)
            od = join(reportdir, d)

            if not exists(od):
                makedirs(od)
                
            f = "%s.report" % f
            fd = open(join(od, f), "wt")
            change.write(opts, outstream=fd)
            fd.close()



def options_magic(options):
    from jardiff import options_magic
    return options_magic(options)



def cli(options, rest):
    options_magic(options)

    left, right = rest[1:3]

    if options.report_dir:
        delta = DistReport(left, right, options, options.shallow)
    else:
        delta = DistChange(left, right, options.shallow)

    delta.check()

    if not options.silent:
        delta.write(options)
    
    if (not delta.is_change()) or delta.is_ignored(options):
        return 0
    else:
        return 1



def create_optparser():
    from jardiff import create_optparser

    parser = create_optparser()

    parser.add_option("--ignore-filenames", action="append", default=[])
    parser.add_option("--shallow", action="store_true", default=False)
    parser.add_option("--report-dir", action="store", default=None)

    return parser



def main(args):
    parser = create_optparser()
    return cli(*parser.parse_args(args))



if __name__ == "__main__":
    sys.exit(main(sys.argv))



#
# The end.