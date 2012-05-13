"""
Unit tests for stem.descriptor.extrainfo_descriptor.
"""

import datetime
import unittest
from stem.descriptor.extrainfo_descriptor import ExtraInfoDescriptor, DirResponses

CRYPTO_BLOB = """
K5FSywk7qvw/boA4DQcqkls6Ize5vcBYfhQ8JnOeRQC9+uDxbnpm3qaYN9jZ8myj
k0d2aofcVbHr4fPQOSST0LXDrhFl5Fqo5um296zpJGvRUeO6S44U/EfJAGShtqWw
7LZqklu+gVvhMKREpchVqlAwXkWR44VENm24Hs+mT3M=
"""

EXTRAINFO_DESCRIPTOR_ATTR = (
  ("extra-info", "ninja B2289C3EAB83ECD6EB916A2F481A02E6B76A0A48"),
  ("published", "2012-05-05 17:03:50"),
  ("router-signature", "\n-----BEGIN SIGNATURE-----%s-----END SIGNATURE-----" % CRYPTO_BLOB),
)

def _make_descriptor(attr = None, exclude = None):
  """
  Constructs a minimal extrainfo descriptor with the given attributes.
  
  Arguments:
    attr (dict)     - keyword/value mappings to be included in the descriptor
    exclude (list)  - mandatory keywords to exclude from the descriptor
  
  Returns:
    str with customized descriptor content
  """
  
  descriptor_lines = []
  if attr is None: attr = {}
  if exclude is None: exclude = []
  attr = dict(attr) # shallow copy since we're destructive
  
  for keyword, value in EXTRAINFO_DESCRIPTOR_ATTR:
    if keyword in exclude: continue
    elif keyword in attr:
      value = attr[keyword]
      del attr[keyword]
    
    # if this is the last entry then we should dump in any unused attributes
    if keyword == "router-signature":
      for attr_keyword, attr_value in attr.items():
        descriptor_lines.append("%s %s" % (attr_keyword, attr_value))
    
    descriptor_lines.append("%s %s" % (keyword, value))
  
  return "\n".join(descriptor_lines)

class TestExtraInfoDescriptor(unittest.TestCase):
  def test_minimal_extrainfo_descriptor(self):
    """
    Basic sanity check that we can parse an extrainfo descriptor with minimal
    attributes.
    """
    
    desc_text = _make_descriptor()
    desc = ExtraInfoDescriptor(desc_text)
    
    self.assertEquals("ninja", desc.nickname)
    self.assertEquals("B2289C3EAB83ECD6EB916A2F481A02E6B76A0A48", desc.fingerprint)
    self.assertTrue(CRYPTO_BLOB in desc.signature)
  
  def test_unrecognized_line(self):
    """
    Includes unrecognized content in the descriptor.
    """
    
    desc_text = _make_descriptor({"pepperjack": "is oh so tasty!"})
    desc = ExtraInfoDescriptor(desc_text)
    self.assertEquals(["pepperjack is oh so tasty!"], desc.get_unrecognized_lines())
  
  def test_proceeding_line(self):
    """
    Includes a line prior to the 'extra-info' entry.
    """
    
    desc_text = "exit-streams-opened port=80\n" + _make_descriptor()
    self._expect_invalid_attr(desc_text)
  
  def test_trailing_line(self):
    """
    Includes a line after the 'router-signature' entry.
    """
    
    desc_text = _make_descriptor() + "\nexit-streams-opened port=80"
    self._expect_invalid_attr(desc_text)
  
  def test_extrainfo_line_missing_fields(self):
    """
    Checks that validation catches when the extra-info line is missing fields
    and that without validation both the nickname and fingerprint are left as
    None.
    """
    
    test_entries = (
      "ninja",
      "ninja ",
      "B2289C3EAB83ECD6EB916A2F481A02E6B76A0A48",
      " B2289C3EAB83ECD6EB916A2F481A02E6B76A0A48",
    )
    
    for entry in test_entries:
      desc_text = _make_descriptor({"extra-info": entry})
      desc = self._expect_invalid_attr(desc_text, "nickname")
      self.assertEquals(None, desc.nickname)
      self.assertEquals(None, desc.fingerprint)
  
  def test_geoip_db_digest(self):
    """
    Parses the geoip-db-digest line with valid and invalid data.
    """
    
    geoip_db_digest = "916A3CA8B7DF61473D5AE5B21711F35F301CE9E8"
    desc_text = _make_descriptor({"geoip-db-digest": geoip_db_digest})
    desc = ExtraInfoDescriptor(desc_text)
    self.assertEquals(geoip_db_digest, desc.geoip_db_digest)
    
    test_entries = (
      "",
      "916A3CA8B7DF61473D5AE5B21711F35F301CE9E",
      "916A3CA8B7DF61473D5AE5B21711F35F301CE9E88",
      "916A3CA8B7DF61473D5AE5B21711F35F301CE9EG",
      "916A3CA8B7DF61473D5AE5B21711F35F301CE9E-",
    )
    
    for entry in test_entries:
      desc_text = _make_descriptor({"geoip-db-digest": entry})
      desc = self._expect_invalid_attr(desc_text, "geoip_db_digest", entry)
  
  def test_dir_response_lines(self):
    """
    Parses the dirreq-v2-resp and dirreq-v3-resp lines with valid and invalid
    data.
    """
    
    for keyword in ("dirreq-v2-resp", "dirreq-v3-resp"):
      attr = keyword.replace('-', '_').replace('dirreq', 'dir').replace('resp', 'responses')
      unknown_attr = attr + "_unknown"
      
      test_value = "ok=0,unavailable=0,not-found=984,not-modified=0,something-new=7"
      desc_text = _make_descriptor({keyword: test_value})
      desc = ExtraInfoDescriptor(desc_text)
      self.assertEquals(0, getattr(desc, attr)[DirResponses.OK])
      self.assertEquals(0, getattr(desc, attr)[DirResponses.UNAVAILABLE])
      self.assertEquals(984, getattr(desc, attr)[DirResponses.NOT_FOUND])
      self.assertEquals(0, getattr(desc, attr)[DirResponses.NOT_MODIFIED])
      self.assertEquals(7, getattr(desc, unknown_attr)["something-new"])
      
      test_entries = (
        "ok=-4",
        "ok:4",
        "ok=4.not-found=3",
      )
      
      for entry in test_entries:
        desc_text = _make_descriptor({keyword: entry})
        desc = self._expect_invalid_attr(desc_text)
        self.assertEqual({}, getattr(desc, attr))
        self.assertEqual({}, getattr(desc, unknown_attr))
  
  def test_percentage_lines(self):
    """
    Uses valid and invalid data to tests lines of the form...
    "<keyword>" num%
    """
    
    for keyword in ('dirreq-v2-share', 'dirreq-v3-share'):
      attr = keyword.replace('-', '_').replace('dirreq', 'dir')
      
      test_entries = (
        ("0.00%", 0.0),
        ("0.01%", 0.0001),
        ("50%", 0.5),
        ("100.0%", 1.0),
      )
      
      for test_value, expected_value in test_entries:
        desc_text = _make_descriptor({keyword: test_value})
        desc = ExtraInfoDescriptor(desc_text)
        self.assertEquals(expected_value, getattr(desc, attr))
      
      test_entries = (
        ("", None),
        (" ", None),
        ("100", None),
        ("100.1%", 1.001),
        ("-5%", -0.05),
      )
      
      for entry, expected in test_entries:
        desc_text = _make_descriptor({keyword: entry})
        self._expect_invalid_attr(desc_text, attr, expected)
  
  def test_timestamp_lines(self):
    """
    Uses valid and invalid data to tests lines of the form...
    "<keyword>" YYYY-MM-DD HH:MM:SS
    """
    
    for keyword in ('published', 'geoip-start-time'):
      attr = keyword.replace('-', '_')
      
      desc_text = _make_descriptor({keyword: "2012-05-03 12:07:50"})
      desc = ExtraInfoDescriptor(desc_text)
      self.assertEquals(datetime.datetime(2012, 5, 3, 12, 7, 50), getattr(desc, attr))
      
      test_entries = (
        "",
        "2012-05-03 12:07:60",
        "2012-05-03 ",
        "2012-05-03",
      )
      
      for entry in test_entries:
        desc_text = _make_descriptor({keyword: entry})
        self._expect_invalid_attr(desc_text, attr)
  
  def test_timestamp_and_interval_lines(self):
    """
    Uses valid and invalid data to tests lines of the form...
    "<keyword>" YYYY-MM-DD HH:MM:SS (NSEC s)
    """
    
    for keyword in ('bridge-stats-end', 'dirreq-stats-end'):
      end_attr = keyword.replace('-', '_').replace('dirreq', 'dir')
      interval_attr = end_attr[:-4] + "_interval"
      
      desc_text = _make_descriptor({keyword: "2012-05-03 12:07:50 (500 s)"})
      desc = ExtraInfoDescriptor(desc_text)
      self.assertEquals(datetime.datetime(2012, 5, 3, 12, 7, 50), getattr(desc, end_attr))
      self.assertEquals(500, getattr(desc, interval_attr))
      
      test_entries = (
        "",
        "2012-05-03 ",
        "2012-05-03",
        "2012-05-03 12:07:60 (500 s)",
        "2012-05-03 12:07:50 (500s)",
        "2012-05-03 12:07:50 (500 s",
        "2012-05-03 12:07:50 (500 )",
      )
      
      for entry in test_entries:
        desc_text = _make_descriptor({keyword: entry})
        desc = self._expect_invalid_attr(desc_text)
        self.assertEquals(None, getattr(desc, end_attr))
        self.assertEquals(None, getattr(desc, interval_attr))
  
  def test_timestamp_interval_and_value_lines(self):
    """
    Uses valid and invalid data to tests lines of the form...
    "<keyword>" YYYY-MM-DD HH:MM:SS (NSEC s) NUM,NUM,NUM,NUM,NUM...
    """
    
    for keyword in ('read-history', 'write-history', 'dirreq-read-history', 'dirreq-write-history'):
      base_attr = keyword.replace('-', '_').replace('dirreq', 'dir')
      end_attr = base_attr + "_end"
      interval_attr = base_attr + "_interval"
      values_attr = base_attr + "_values"
      
      test_entries = (
        ("", []),
        (" ", []),
        (" 50,11,5", [50, 11, 5]),
      )
      
      for test_values, expected_values in test_entries:
        desc_text = _make_descriptor({keyword: "2012-05-03 12:07:50 (500 s)%s" % test_values})
        desc = ExtraInfoDescriptor(desc_text)
        self.assertEquals(datetime.datetime(2012, 5, 3, 12, 7, 50), getattr(desc, end_attr))
        self.assertEquals(500, getattr(desc, interval_attr))
        self.assertEquals(expected_values, getattr(desc, values_attr))
      
      test_entries = (
        "",
        "2012-05-03 ",
        "2012-05-03",
        "2012-05-03 12:07:60 (500 s)",
        "2012-05-03 12:07:50 (500s)",
        "2012-05-03 12:07:50 (500 s",
        "2012-05-03 12:07:50 (500 )",
        "2012-05-03 12:07:50 (500 s)11",
      )
      
      for entry in test_entries:
        desc_text = _make_descriptor({keyword: entry})
        desc = self._expect_invalid_attr(desc_text)
        self.assertEquals(None, getattr(desc, end_attr))
        self.assertEquals(None, getattr(desc, interval_attr))
        self.assertEquals(None, getattr(desc, values_attr))
  
  def test_locale_mapping_lines(self):
    """
    Uses valid and invalid data to tests lines of the form...
    "<keyword>" CC=N,CC=N,...
    """
    
    for keyword in ('dirreq-v2-ips', 'dirreq-v3-ips', 'dirreq-v2-reqs', 'dirreq-v3-reqs', 'geoip-client-origins', 'bridge-ips'):
      attr = keyword.replace('-', '_').replace('dirreq', 'dir').replace('reqs', 'requests')
      
      test_entries = (
        ("", {}),
        ("uk=5,de=3,jp=2", {'uk': 5, 'de': 3, 'jp': 2}),
      )
      
      for test_value, expected_value in test_entries:
        desc_text = _make_descriptor({keyword: test_value})
        desc = ExtraInfoDescriptor(desc_text)
        self.assertEquals(expected_value, getattr(desc, attr))
      
      test_entries = (
        "uk=-4",
        "uki=4",
        "uk:4",
        "uk=4.de=3",
      )
      
      for entry in test_entries:
        desc_text = _make_descriptor({keyword: entry})
        desc = self._expect_invalid_attr(desc_text, attr, {})
  
  def _expect_invalid_attr(self, desc_text, attr = None, expected_value = None):
    """
    Asserts that construction will fail due to desc_text having a malformed
    attribute. If an attr is provided then we check that it matches an expected
    value when we're constructed without validation.
    """
    
    self.assertRaises(ValueError, ExtraInfoDescriptor, desc_text)
    desc = ExtraInfoDescriptor(desc_text, validate = False)
    
    if attr:
      # check that the invalid attribute matches the expected value when
      # constructed without validation
      
      self.assertEquals(expected_value, getattr(desc, attr))
    else:
      # check a default attribute
      self.assertEquals("ninja", desc.nickname)
    
    return desc

