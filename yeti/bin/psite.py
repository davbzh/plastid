#!/usr/bin/env python
"""This script estimates P-site offsets, stratified by read length,
in a ribosome profiling dataset by calculating metagene averages for each
read length surrounding the start codon, mapping the reads to their fiveprime
ends. The start codon peak for each read length is heuristically identified
as the largest peak upstream of the start codon. The distance between that
peak and the start codon itself is taken to be the P-site offset for that
read length.

Note, users should examine output files to make sure these estimates are reasonable.
For this reason, in addition to the P-site offsets, full metagene profiles are
exported as tables and graphics.

This script will fail if run on a dataset that lacks distinct start codon peaks.

Output files
------------
    ${OUTBASE}_p_offsets.txt
        Tab-delimited text file with two columns. The first is read length,
        and the second the offset from the fiveprime end of that read length
        to the ribosomal P-site. Can be used with --fiveprime_variable mapping
        for other scripts in this dataset.

    ${OUTBASE}_p_offsets.svg
        Plot of metagene profiles for each read length, mapped to their 
        fiveprime ends. 

    ${OUTBASE}_metagene_profiles.txt
        Metagene profiles, stratified by read length, before P-site offsets
        are applied

    ${OUTBASE}_${K}_rawcounts.txt
        Raw count vectors for each metagene window specified in input ROI file,
        without P-site mapping rules applied, for reads of length K

    ${OUTBASE}_${K}_normcounts.txt
        Normalized count vectors for each metagene window specified in input ROI file,
        without P-site mapping rules applied, for reads of length K

where ${OUTBASE} is supplied by the user.
"""
import sys
import matplotlib
matplotlib.use("Agg")
import numpy
import argparse
import matplotlib.pyplot as plt
import inspect

from collections import OrderedDict

from yeti.util.scriptlib.argparsers import get_genome_array_from_args,\
                                                      get_alignment_file_parser
from yeti.genomics.roitools import SegmentChain
from yeti.util.array_table import ArrayTable
from yeti.util.io.openers import get_short_name, argsopener, NullWriter, opener
from yeti.util.io.filters import NameDateWriter
from yeti.genomics.genome_array import SizeFilterFactory
from yeti.util.scriptlib.help_formatters import format_module_docstring
from yeti.util.services.decorators import catch_warnings


printer = NameDateWriter(get_short_name(inspect.stack()[-1][1]))

disabled_args = ["normalize",
                 "big_genome",
                 "nibble",
                 "offset",
                 "fiveprime_variable",
                 "fiveprime",
                 "threeprime",
                 "center"]

@catch_warnings("ignore")
def do_count(roi_table,gnd,norm_start,norm_end,min_counts,min_len,max_len,printer=NullWriter()):
    """Counts the number of reads at each position in each ROI, and normalizes
    each resulting vector by the total number of counts in a normalization
    region specified by norm_start and norm_end
    
    Parameters
    ----------
    roi_table : |ArrayTable|
        |ArrayTable| specifying regions of interest, generated
        by :py:meth:`do_generate`
    
    gnd : |BAMGenomeArray|
        Count data
    
    norm_start : int
        Coordinate in ROI specifying normalization region start
    
    norm_end : int
        Coordinate in ROI specifying normalization region end
    
    min_counts : float
        Minimum number of counts in ROI to be included in metagene profile

    min_len : int
        Minimum read length to include
    
    max_len : int
        Maximum read length to include

        
    Returns
    -------
    dict
        Dictionary of ``numpy.ndarray`` s of raw counts at each position (column)
        for each ROI (row)
    
    dict
        Dictionary of ``numpy.ndarray`` s of raw counts at each position (column)
        for each ROI (row), normalized by the total number of counts in that row
        from norm_start to norm_end
    
    |ArrayTable|
        Metagene profile of median normalized counts at each position across
        all ROIs, and the number of genes included in the calculation of each
        median, stratified by read length
    """
    window_size    = roi_table["window_size"][0]
    upstream_flank = roi_table["zero_point"][0]
    
    raw_count_dict  = OrderedDict()
    norm_count_dict = OrderedDict()
    for i in range(min_len,max_len+1):
        raw_count_dict[i] = numpy.ma.MaskedArray(numpy.tile(numpy.nan,(len(roi_table),window_size)))
        raw_count_dict[i].mask = numpy.tile(False,raw_count_dict[i].shape)
    
    for i in range(len(roi_table)):
        if i % 1000 == 0:
            printer.write("Counted %s ROIs..." % (i+1))
            
        roi    = SegmentChain.from_str(roi_table["region"][i])
        mask   = SegmentChain.from_str(roi_table["masked"][i])
        roi.add_masks(*mask)
        valid_mask = roi.get_valid_counts(gnd).mask
        
        offset = int(round((roi_table["alignment_offset"][i])))
        assert offset + roi.get_length() <= window_size
        
        count_vectors = {}
        for k in raw_count_dict:
            count_vectors[k] = []

        for iv in roi:
            reads = gnd.get_reads(iv)
            read_dict = {}
            for k in raw_count_dict:
                read_dict[k] = []

            for read in filter(lambda x: len(x.positions) in read_dict,reads):
                read_dict[len(read.positions)].append(read)
            
            for read_length in read_dict:
                count_vector = list(gnd.map_fn(read_dict[read_length],iv)[1])
                count_vectors[read_length].extend(count_vector)
                
        for read_length in raw_count_dict:
            if roi.strand == "-":
                count_vectors[read_length] = count_vectors[read_length][::-1]

            raw_count_dict[read_length][i,offset:offset+roi.get_length()]      = numpy.array(count_vectors[read_length])
            raw_count_dict[read_length].mask[i,offset:offset+roi.get_length()] = valid_mask
    
    profile_table = { "x" : numpy.arange(-upstream_flank,window_size-upstream_flank) }
    
    printer.write("Counted %s ROIs total." % (i+1))
    for read_length in raw_count_dict:
        raw_count_dict[read_length] = numpy.ma.masked_invalid(raw_count_dict[read_length])
        denominator = raw_count_dict[read_length][:,norm_start:norm_end].sum(1)
        norm_count_dict[read_length] = (1.0*raw_count_dict[read_length].T / denominator).T
    
        norm_counts = numpy.ma.masked_invalid(norm_count_dict[read_length])
    
        profile   = numpy.ma.median(norm_counts[denominator >= min_counts],axis=0)
        num_genes = ((~norm_counts.mask)[denominator >= min_counts]).sum(0) 
        
        profile_table["%s-mers" % read_length]         = profile
        profile_table["%s_regions_counted" % read_length] = num_genes
        
    profile_table = ArrayTable(profile_table)
    
    return raw_count_dict, norm_count_dict, profile_table


def main(argv=sys.argv[1:]):
    """Command-line program
    
    Parameters
    ----------
	argv : list, optional
		A list of command-line arguments, which will be processed
		as if the script were called from the command line if
		:py:func:`main` is called directrly.

		Default: sys.argv[1:] (actually command-line arguments)
    """
    alignment_file_parser = get_alignment_file_parser(disabled=disabled_args,
                                                      input_choices=["BAM"])
    
    parser = argparse.ArgumentParser(description=format_module_docstring(__doc__),
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     parents=[alignment_file_parser])
    
    parser.add_argument("--min_counts",type=int,default=10,metavar="N",
                         help="Minimum counts required in normalization region "+
                              "to be included in metagene average (Default: 10)")
    parser.add_argument("--norm_region",type=int,nargs=2,metavar="N",
                         default=(70,100),
                         help="Portion of ROI against which each individual profile"+
                              " will be normalized. Specify two integers, in nucleotide"+
                              " distance, from 5' end of ROI. (Default: 70 100)")
    parser.add_argument("--require_upstream",default=False,action="store_true",
                        help="If supplied, the P-site offset is taken to be the distance "+
                             "between the largest peak upstream of the start codon and "+
                             "the start codon itself. Otehrwise, the P-site offset is taken "+
                             "to be the distance between the largest peak in the entire ROI "+
                             "and the start codon."
                        )

    parser.add_argument("--default",type=int,default=13,
                        help="Default fiveprime P-site offset for read lengths that are not present or evaluated in the dataset (Default: 13)")

    parser.add_argument("roi_file",type=str,
                        help="ROI file surrounding start codons, from metagene `generate` subprogram")
    
    parser.add_argument("outbase",type=str,help="Basename for output files")
    
    # set manual options
    args = parser.parse_args(argv)
    args.mapping = "fiveprime"
    args.offset  = 0
    args.nibble  = 0
    
    # process arguments
    printer.write("Opening ROI file %s..." % args.roi_file)
    with opener(args.roi_file) as roi_fh:
        roi_table = ArrayTable.from_file(roi_fh)
        roi_fh.close()
        
    printer.write("Opening count files %s..." % ",".join(args.count_files))
    gnd = get_genome_array_from_args(args,printer=printer,disabled=disabled_args)
    
    # remove default size filters
    my_filters = gnd._filters.keys()
    for f in my_filters:
        gnd.remove_filter(f)

    count_dict, norm_count_dict, metagene_profile = do_count(roi_table,
                                                             gnd,
                                                             args.norm_region[0],
                                                             args.norm_region[1],
                                                             args.min_counts,
                                                             args.min_length,
                                                             args.max_length,
                                                             printer=printer)
    
    profile_fn = "%s_metagene_profiles.txt" % args.outbase
    with argsopener(profile_fn,args,"w") as metagene_out:
        metagene_profile.to_file(metagene_out,
                                  keyorder=["x"]+["%s-mers" % X for X in range(args.min_length,
                                                                               args.max_length+1)])
        metagene_out.close()

    for k in count_dict:
        count_fn     = "%s_%s_rawcounts.txt"  % (args.outbase,k)
        normcount_fn = "%s_%s_normcounts.txt" % (args.outbase,k)
        numpy.savetxt(count_fn,count_dict[k],delimiter="\t")
        numpy.savetxt(normcount_fn,norm_count_dict[k],delimiter="\t")
        
    # find max offset, plot, write dict
    offset_dict = OrderedDict() 
    fig = plt.figure()
    ax  = plt.gca()
    plt.xlabel("nt from CDS start (5' end mapping)")
    plt.ylabel("Normalized read density")
    plt.title("Fiveprime read offsets by length")
    x = metagene_profile["x"]
    mask = numpy.tile(True,len(x)) if args.require_upstream is False else (x <= 0)

    for k in range(args.min_length,args.max_length+1):
        y = metagene_profile["%s-mers" % k]
        # if y is nans or zeros, no offset is found
        if mask.sum() == numpy.isnan(y[mask]).sum() or y[mask].sum() == 0:
            offset = args.default
        else:
            offset = -x[y[mask].argmax()]
            
        offset_dict[k] = offset
        if not numpy.isnan(y.max()):
            lines = plt.plot(x,y)
            plt.text(-offset,
                     y[mask].max(),
                     "%s: %s" % (k,offset),
                     color=lines[0].get_color(),
                     ha="center",
                     transform=matplotlib.transforms.offset_copy(ax.transData,fig,
                                                                 x=3.0,y=3.0,units="points")
                    )   

    plt.xlim(x.min(),x.max())

    # save data as p-site offset table
    fn = "%s_p_offsets.txt" % args.outbase
    fout = argsopener(fn,args)
    fout.write("#length\tp_offset\n")
    for k in offset_dict:
        fout.write("%s\t%s\n" % (k,offset_dict[k]))
    
    fout.write("default\t%s" % args.default)
    
    fout.close()

    # save plot
    plt.savefig("%s_p_offsets.svg" % args.outbase)

    printer.write("Done.")

if __name__ == "__main__":
    main()
