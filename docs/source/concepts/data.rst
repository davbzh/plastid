Categories of genomics data
===========================
This document contains very, very brief overviews of the types of data
encountered in genomics, and of some common file formats.

.. _quickstart-data:

Types of data
-------------

Generally speaking, genomics data comes in a few flavors:

    Sequence
        The nucleotide sequence of a chromosome, contig, transcript,
        or a set of these. These are typically maintained by public databases,
        such as `UCSC <UCSC genome browser>`_, `Ensembl`_, and `RefSeq`_. The
        genome sequence for a given organism frequently is available in several
        editions, called :term:`builds <genome build>` or :term:`assemblies <genome build>`.
    
    :term:`Annotations <annotation>`
        Descriptions of features -- e.g. genes, transcripts, SNPs, start codons
        -- that appear in genomes or transcripts. Annotations typically include
        coordinates (chromosome name, chromosome positions, and a chromosome
        strand), as well as properties (gene name, function, GO terms, et c) of
        a given feature.
        
        :term:`Annotations <annotation>` are maintained by the same public
        databases that maintain sequence information, because the coordinates
        in each annotation are specific to the :term:`genome build` upon which
        it is based. In other words, annotations and sequences must be matched!
        Pay particular attention to this when downloading annotations as 
        supplemental data from a journal article.
        
    Quantitative data
        Any kind of numerical value associated with a chromosomal
        position. For example, the degree of phylogenetic conservation between a 
        set of organisms, at each position in the genome. Or, the strength of 
        transcription factor binding to a chromosomal position in a ChIP-seq dataset.
        
        Because quantitative data associates values with chromosomal coordinates,
        it can be considered an :term:`annotation` of sorts. It is therefore
        important again to make sure that the coordinates in your data file
        match the :term:`genome build` used by your feature :term:`annotation`
        and/or :term:`read alignments`.
        
    :term:`Read alignments <read alignments>`
        A record matching a short sequence of DNA to a region of identical or similar
        sequence in a genome. In a :term:`high-throughput sequencing` experiment,
        alignment of short reads identifies the genomic coordinates from which
        each read presumably derived.
        
        :term:`Read alignments <read alignments>` can be produced by running
        sequencing data through alignment programs,
        such as `Bowtie`_, `Tophat`_, or `BWA`_. 
        
        Finally, :term:`Read alignments <read alignments>`
        can be converted to quantitative data by applying a :term:`mapping rule`,
        to convert the read to a count. For example, one could count the number
        of 5' ends of reads that align to each position in a genome. For
        an in-depth discussion of this, see :doc:`concepts/mapping_rules`.


Formats of data
---------------
One of the design goals of :data:`yeti` is to insulate users from the esoterica
of the various file formats used in genomics. But, two points are relevant:

  #. It is important for users to recognize the file types names in order to 
     identify the files they have or need to download.
     
  #. Some file formats are *indexed* and others are not. Indexed files are
     memory-efficient, because computer programs don't need to read the entire
     file to find the data of interest; instead, they can read the index and
     just fetch the desired portion of the data.
     
     However, indexed files are frequently compressed, which can make reading them 
     slower to parse. For small genomes that don't use much memory in the first
     place (e.g. yeast, *E. coli*), the meagre memory savings aren't worth this
     speed cost. The exception is for short :term:`read alignments`, where indexed
     `BAM`_ files are universally recommended. 

.. TODO: update when format support changes

Below is a table of commonly used file formats. At present, :data:`yeti` handles
all of these except `BigWig`_, either natively or via `Pysam`_ (`BAM`_ files),
`Biopython`_ (`FASTA`_), or `2bitreader`_ (`2bit <twobit>`_).

    =====================   ===================================   ===================
    **Data type**           **Unindexed formats**                 **Indexed formats**
    ---------------------   -----------------------------------   -------------------
    Sequence                `FASTA`_                              `2bit <twobit>`_
    
    Annotations             `BED`_, `GTF2`_, `GFF3`_, `PSL`_      `BigBed`_ 
    
    Quantitative data       `bedGraph`_, `wiggle`_                `BigWig`_
    
    Read alignments         `bowtie`_, `PSL`_                     `BAM`_ 
    =====================   ===================================   ===================
 
 
Finally, for large genomes, `BED`_, `GTF2`_, `GFF3`_, and `PSL`_ files can be
indexed via `tabix`_. :data:`yeti` supports (via `pysam`_) reading of
`tabix`_-compressed files too.


Why are there so many formats?
------------------------------

There are a number of answers to this:

 #. Genomics is a young science, and for a long time there was no consensus
    on how best to store data. This dialogue is, in fact, still ongoing.
     
 #. It became apparent that file formats that work well with small genomes
    become very onerous for mammalian-sized genomes. This is why, for example,
    the `2bit <twobit>`_, `BigBed`_, and `BigWig`_ formats were created. 

 #. The various file formats have their own strengths and weaknesses. For example,
    we'll compare transcript annotations in `BED`_ and `GFF3`_ format:
     
      - `BED`_ files can contain one multi-exon transcript in a single line.
        This means that if you are, for example, tabulating gene expression 
        values, you can read one line of a file, process the transcript, 
        count the reads covering it, and then forget that transcript before
        moving on to the next record.
      
        In contrast, `GFF3`_ files are hierarchical. Each exon in a multi-exon
        transcript would have its own line. Therefore, in order to
        assemble a transcript from a `GFF3`_ file, many records need to be
        held in memory until the `GFF3`_ reader is confidant it has read all of
        the records that are members of the transcript of interest. Frequently,
        a `GFF3`_ reader has know way of knowing that *a priori*, so many readers
        end up holding all records in memory before processing any individual
        transcript. This costs a tremendous amount of memory, and time, compared
        to processing a `BED`_ file.

      - However, `BED`_ files contain no feature annotation information beyond
        a feature name. So, using only a `BED`_ file, one cannot, for example,
        group transcripts by gene without some external source of information.
        `GFF3`_ files, in contrast, offer the ability to include arbitrarily
        complex information (parent-child relationships, paragraphs desribing
        gene function, citations, GO terms, et c) for any given feature.

For more info, see:

  - the `UCSC file format FAQ <http:/genome.ucsc.edu/FAQ/FAQformat.html>`_,
    which discusses various formats in detail
    
  - the `GFF3`_ specification
  
  - the `GTF2`_ specification


Getting the most out of your time & data
----------------------------------------

Starting a new type of analysis is rarely straightfoward. But, it is possible 
to save some time by following several practices:

 #. Make sure your :term:`annotation` matches your :term:`genome build`. e.g.
    do not use the *mm9* mouse genome annotation with the *mm10* sequence
    assembly. Do not mix `Ensembl`_'s human genome build *GRCh38* and
    `UCSC`_'s similar-but-still-different *hg38*.

 #. If using a large genome (e.g. *Drosophila* or larger), consider using
    non-hierarchical (e.g. `BED`_) and possibly indexed (e.g. `BigBed`_, `BigWig`_ ) file
    types instead of non-indexed formats.

 #. Work from alignments in `BAM`_, rather than `bowtie`_, format.