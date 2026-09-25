<?xml version="1.0" encoding="UTF-8"?>
<!--
  BC Studies — JATS house rules (ISO Schematron)

  These are the constraints the DTD structurally cannot express: renderer
  quirks, aggregator expectations, house metadata policy, and link integrity
  beyond what ID/IDREF gives you.

  Run with lxml (already a dependency):

      from lxml import etree
      from lxml.isoschematron import Schematron
      sch = Schematron(etree.parse("bcs-house-rules.sch"), store_report=True)
      ok  = sch.validate(doc)          # doc = etree parse of the generated JATS

  Roles: error = will break a consumer. warning = probably wrong.
         info  = worth a glance butnot necessarily a defect.
-->
<schema xmlns="http://purl.oclc.org/dsdl/schematron"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        queryBinding="xslt">

  <title>BC Studies JATS house rules</title>

  <ns prefix="xlink" uri="http://www.w3.org/1999/xlink"/>
  <ns prefix="mml"   uri="http://www.w3.org/1998/Math/MathML"/>

  <xsl:key name="ids"    match="*[@id]" use="@id"/>
  <xsl:key name="idrefs" match="xref"   use="@rid"/>

  <!-- ================================================================
       1. eLife/Lens renderer constraints
       These are the "tag abuse" rules. They fire only on the "lens"
       profile, which BC Studies no longer publishes: the HTML galley is
       built from it, but the XML itself is not uploaded to OJS.
       ================================================================ -->
  <pattern id="lens">

    <!-- Each generated file declares its own profile in <custom-meta>, so
         these rules only fire on the galley copy. -->
    <let name="profile"
         value="string(//custom-meta[meta-name='generator-profile']/meta-value)"/>
    <let name="is-archival" value="$profile = 'archival'"/>

    <rule context="ref">
      <assert test="$is-archival or element-citation" role="error">
        Lens renders the References panel only from &lt;element-citation&gt;.
        This &lt;ref&gt; has none and will not appear.
      </assert>
      <assert test="$is-archival or .//person-group" role="error">
        Lens DROPS any &lt;ref&gt; with no &lt;person-group&gt;.
        Author-less works (films, websites) need &lt;person-group&gt;&lt;anonymous/&gt;&lt;/person-group&gt;.
      </assert>
    </rule>

    <rule context="element-citation//person-group">
      <assert test="$is-archival or name or anonymous or collab or etal" role="error">
        Lens reads author names only from &lt;name&gt;, never &lt;string-name&gt;.
      </assert>
    </rule>

    <rule context="back/fn-group">
      <report test="not($is-archival)" role="warning">
        This Lens build never renders a back-matter &lt;fn-group&gt; (its notes
        hook is an empty stub). Notes belong in a body
        &lt;sec sec-type="endnotes"&gt; instead. Correct for the archival
        profile; wrong for the galley.
      </report>
    </rule>

  </pattern>

  <!-- ================================================================
       1b. The archival copy must NOT carry the workarounds.
       ================================================================ -->
  <pattern id="archival">

    <let name="aprofile"
         value="string(//custom-meta[meta-name='generator-profile']/meta-value)"/>

    <rule context="anonymous">
      <report test="$aprofile = 'archival'" role="error">
        The archival copy must not assert &lt;anonymous/&gt; — that is a Lens
        workaround, not a fact about the work.
      </report>
    </rule>

    <!-- Note: there is deliberately no "article-title without source" check
         here. The archival branch of build_element_citation() structurally
         cannot file a whole work under <article-title>, and an entry that
         genuinely has a quoted title but no container (a conference paper,
         an unpublished manuscript) is perfectly normal.  -->

  </pattern>

  <!-- ================================================================
       1c. Provenance must travel with the file.
       ================================================================ -->
  <pattern id="provenance">
    <rule context="article-meta">
      <assert test="custom-meta-group/custom-meta[meta-name='generator-profile']"
              role="error">
        No profile recorded. Every generated file must say which profile
        produced it, or nobody can tell later what was done to it and why.
      </assert>
      <assert test="custom-meta-group/custom-meta[meta-name='generator']"
              role="warning">
        No generator/version recorded.
      </assert>
    </rule>
  </pattern>

  <!-- ================================================================
       2. Aggregator expectations (ProQuest et al.)
       ================================================================ -->
  <pattern id="aggregator">
    <rule context="ref">
      <assert test="mixed-citation" role="warning">
        Aggregators want the exact printed text of the entry.
        Add a &lt;mixed-citation&gt; alongside the &lt;element-citation&gt;.
      </assert>
    </rule>
  </pattern>

  <!-- ================================================================
       3. House metadata policy
       ================================================================ -->
  <pattern id="house-metadata">

    <rule context="article-meta">
      <assert test="pub-date" role="error">
        No &lt;pub-date&gt;. OJS will not show a publication date.
        Set "Published online" in the Metadata tab.
      </assert>
      <assert test="article-id[@pub-id-type='doi']" role="warning">
        No article DOI. BC Studies registers a DOI per article in OJS --
        copy it from the submission into the DOI field (Metadata tab).
      </assert>
      <assert test="fpage and lpage" role="error">
        Missing page range (fpage/lpage).
      </assert>
      <assert test="not(fpage and lpage)
                    or not(number(fpage) = number(fpage))
                    or not(number(lpage) = number(lpage))
                    or number(lpage) &gt;= number(fpage)" role="error">
        lpage is before fpage.
      </assert>
      <assert test="title-group/article-title[normalize-space()]" role="error">
        Article has no title. If it came from a titleless piece, the TOC
        backfill did not find it.
      </assert>
    </rule>

    <rule context="contrib[@contrib-type='author']">
      <assert test="name/surname[normalize-space()] or collab or anonymous" role="error">
        Author contrib with no surname.
      </assert>
    </rule>

  </pattern>

  <!-- ================================================================
       4. Link integrity beyond DTD ID/IDREF
       (DTD catches dangling @rid; it cannot check that the target is the
       RIGHT KIND of thing, or that references are used at all.)
       ================================================================ -->
  <pattern id="links">

    <rule context="xref[@ref-type='bibr']">
      <assert test="key('ids', @rid)/self::ref" role="error">
        Bibliographic xref points at something that is not a &lt;ref&gt;.
      </assert>
    </rule>

    <rule context="xref[@ref-type='fig']">
      <assert test="key('ids', @rid)/self::fig" role="error">
        Figure xref points at something that is not a &lt;fig&gt;.
      </assert>
    </rule>

    <rule context="xref[@ref-type='fn']">
      <assert test="key('ids', @rid)" role="error">
        Note callout points at a missing note.
      </assert>
    </rule>

    <rule context="ref">
      <report test="not(key('idrefs', @id))" role="info">
        Reference is never cited in the text. Expected for a Bibliography;
        for a reference list it usually means an unresolved citation.
      </report>
    </rule>

  </pattern>

  <!-- ================================================================
       5. Structure sanity
       ================================================================ -->
  <pattern id="structure">

    <rule context="sec">
      <assert test="title[normalize-space()]" role="warning">
        &lt;sec&gt; with no &lt;title&gt; — a heading was probably lost.
      </assert>
    </rule>

    <rule context="body">
      <report test="count(sec[@sec-type='endnotes']) &gt; 1" role="error">
        More than one endnotes section.
      </report>
    </rule>

    <rule context="fig">
      <assert test="graphic/@xlink:href[normalize-space()]" role="error">
        Figure has no graphic reference.
      </assert>
    </rule>

  </pattern>

</schema>
